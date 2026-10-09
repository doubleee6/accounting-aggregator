# -*- coding: utf-8 -*-
"""会计视野论坛「登录态」正文抓取（Discuz）。

正文需登录才能访问，凭证通过浏览器 Cookie 提供，来源优先级：
1. 环境变量 BBS_COOKIE（GitHub Actions 用 Secrets 注入）
2. 本地文件 .bbs_cookie（不入库，.gitignore 忽略）

安全约定：Cookie 等同账号凭证，绝不写入代码或提交仓库。
"""
import os
import re
import time

import requests

BASE = "https://bbs.esnai.cn"

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

COOKIE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".bbs_cookie")


def load_cookie():
    """读取 Cookie：环境变量优先，其次本地文件。返回空串表示未配置。"""
    ck = (os.environ.get("BBS_COOKIE") or "").strip()
    if ck:
        return ck
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def _session():
    s = requests.Session()
    s.trust_env = False  # 忽略系统代理
    s.headers.update({
        "User-Agent": _UA,
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": f"{BASE}/forum.php",
    })
    ck = load_cookie()
    if ck:
        s.headers["Cookie"] = ck
    return s


def _clean_html(seg):
    """HTML 片段转纯文本：保留段落换行，去标签与多余空白。"""
    seg = re.sub(r"<script.*?</script>", "", seg, flags=re.S | re.I)
    seg = re.sub(r"<style.*?</style>", "", seg, flags=re.S | re.I)
    seg = re.sub(r"<br\s*/?>", "\n", seg, flags=re.I)
    seg = re.sub(r"</(p|div|tr|li|h\d)>", "\n", seg, flags=re.I)
    seg = re.sub(r"<[^>]+>", "", seg)
    seg = (seg.replace("&nbsp;", " ").replace("&amp;", "&")
              .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))
    seg = re.sub(r"[ \t\u3000]+", " ", seg)
    seg = re.sub(r"\n{3,}", "\n\n", seg)
    return seg.strip()


def _extract_posts(html):
    """提取所有楼层（主楼 + 回帖）。

    返回 [{pid, floor, author, date, text}]，floor=0 表示主楼。
    Discuz 正文节点为 <td class="t_f" id="postmessage_<pid>">；
    作者在 <div class="authi"> 里的首个用户链接；楼层时间在
    <em id="authorposton<pid>">…</em>。
    """
    posts = []
    # 按 postmessage_<pid> 切块，块尾到下一个 postmessage 或页面尾部
    marks = list(re.finditer(r'id="postmessage_(\d+)"', html))
    for idx, m in enumerate(marks):
        pid = m.group(1)
        start = m.start()
        end = marks[idx + 1].start() if idx + 1 < len(marks) else len(html)
        chunk = html[start:end]

        # 正文：t_f 单元格 → 直到 </td>
        tm = re.search(
            r'<td[^>]*class="[^"]*\bt_f\b[^"]*"[^>]*id="postmessage_\d+"[^>]*>(.*?)</td>',
            chunk, re.S,
        )
        if not tm:
            tm = re.search(r'id="postmessage_\d+"[^>]*>(.*?)</td>', chunk, re.S)
        text = _clean_html(tm.group(1)) if tm else ""
        if not text:
            continue

        # 作者：authi 区块里的首个用户链接
        author = ""
        am = re.search(r'<div[^>]*class="[^"]*\bauthi\b[^"]*"[^>]*>(.*?)</div>', chunk, re.S)
        if am:
            um = re.search(r'<a[^>]*href="[^"]*space-uid-\d+[^"]*"[^>]*>([^<]+)</a>', am.group(1))
            if um:
                author = _clean_html(um.group(1))

        # 时间：<em id="authorposton{pid}">…2026-9-29 10:30…</em>
        date = ""
        dm = re.search(rf'id="authorposton{pid}"[^>]*>(.*?)</em>', chunk, re.S)
        if dm:
            dt = _clean_html(dm.group(1))
            dm2 = re.search(r"\d{4}-\d{1,2}-\d{1,2}(?:\s+\d{1,2}:\d{2})?", dt)
            if dm2:
                date = dm2.group(0)

        posts.append({
            "pid": pid,
            "floor": idx,
            "author": author,
            "date": date,
            "text": text,
        })
    return posts


def fetch_thread_full(url, session=None, max_pages=5):
    """抓取帖子全部楼层（主楼 + 回帖，必要时翻页）。

    返回 (content, title, reply_count)：
      content 为合并后的文本，回帖以「【回帖N · 作者】」分隔；
      未登录 / 无权限时 content 为空串。
    """
    s = session or _session()
    base = re.sub(r"-\d+-1\.html.*$", "", url)  # 去掉页码，便于拼分页
    all_posts, title, seen = [], "", set()

    for page in range(1, max_pages + 1):
        u = url if page == 1 else f"{base}-{page}-1.html"
        try:
            resp = s.get(u, timeout=25)
        except Exception:
            if page == 1:
                raise
            break
        resp.encoding = "gbk"
        html = resp.text

        if page == 1:
            if ("您需要登录" in html or "抱歉，本帖要求阅读权限" in html
                    or "登录后才能查看" in html):
                return "", "", 0
            tm = re.search(r"<title>(.*?)</title>", html, re.S)
            title = _clean_html(tm.group(1)) if tm else ""
            title = re.sub(r"\s*[-_].*?Powered by Discuz.*$", "", title, flags=re.I).strip()

        posts = _extract_posts(html)
        fresh = [p for p in posts if p["pid"] not in seen]
        for p in fresh:
            seen.add(p["pid"])
        all_posts.extend(fresh)

        # 该页无新增，或已到最后一页 → 停
        if not fresh:
            break
        if not re.search(rf"thread-\d+-{page + 1}-1\.html", html):
            break
        time.sleep(0.4)

    if not all_posts:
        return "", title, 0

    parts = []
    for p in all_posts:
        if p["floor"] == 0:
            parts.append(p["text"])
        else:
            who = f" · {p['author']}" if p["author"] else ""
            when = f" · {p['date']}" if p["date"] else ""
            parts.append(f"【回帖{p['floor']}{who}{when}】\n{p['text']}")
    return "\n\n".join(parts), title, max(0, len(all_posts) - 1)


def fetch_thread(url, session=None):
    """兼容旧调用：返回 (content, title)，content 含主楼与回帖。"""
    content, title, _ = fetch_thread_full(url, session=session)
    return content, title


def fetch_threads(urls, interval=1.2, on_progress=None):
    """批量抓取，返回 {url: content} 字典。带统一会话与限速。"""
    s = _session()
    out = {}
    for i, url in enumerate(urls, 1):
        try:
            content, _ = fetch_thread(url, session=s)
        except Exception as e:
            content = ""
            print(f"  正文失败: {url} -> {e}")
        out[url] = content
        if on_progress:
            on_progress(i, len(urls), url, len(content))
        time.sleep(interval)
    return out
