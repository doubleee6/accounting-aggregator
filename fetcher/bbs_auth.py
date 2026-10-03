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


def fetch_thread(url, session=None):
    """抓取帖子正文（主楼）。返回 (content, title)；未登录或无权限时 content 为空。"""
    s = session or _session()
    for attempt in range(3):
        try:
            resp = s.get(url, timeout=25)
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    resp.encoding = "gbk"
    html = resp.text

    if "您需要登录" in html or "抱歉，本帖要求阅读权限" in html or "登录后才能查看" in html:
        return "", ""

    title_m = re.search(r'<title>(.*?)</title>', html, re.S)
    title = _clean_html(title_m.group(1)) if title_m else ""
    title = re.sub(r"\s*[-_].*?Powered by Discuz.*$", "", title, flags=re.I).strip()

    # 主楼正文：Discuz 标准为 <td class="t_f" id="postmessage_xxx">
    m = re.search(r'<td[^>]*class="t_f"[^>]*id="postmessage_\d+"[^>]*>(.*?)</td>', html, re.S)
    if not m:
        m = re.search(r'<div[^>]*id="postmessage_\d+"[^>]*>(.*?)</div>', html, re.S)
    if not m:
        return "", title
    return _clean_html(m.group(1)), title


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
