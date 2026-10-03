# -*- coding: utf-8 -*-
"""会计视野论坛（Discuz）抓取：通过 RSS 获取板块帖子。

论坛帖子正文需登录（游客无法访问详情页），但 RSS 出口公开可用，
包含标题、链接、正文摘要、作者、发布时间，足够聚合展示。
"""
import re
import time
import xml.etree.ElementTree as ET
from datetime import timedelta
from email.utils import parsedate_to_datetime

import requests

from .common import HEADERS, make_id

BOARDS = [
    {"fid": 5, "name": "内部审计"},
    {"fid": 7, "name": "CPA业务探讨"},
]


def _get_rss(fid):
    """获取 RSS，带重试（bbs.esnai.cn 偶发断连）。"""
    url = f"https://bbs.esnai.cn/forum.php?mod=rss&fid={fid}"
    last_err = None
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=25)
            resp.encoding = "gbk"  # RSS 为 GBK 编码，显式指定避免乱码
            return resp.text
        except Exception as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise last_err


def _parse_date(pubdate):
    """pubDate 形如 'Thu, 30 Jul 2026 01:46:08 +0000'，转北京时间 YYYY-MM-DD。"""
    try:
        dt = parsedate_to_datetime(pubdate) + timedelta(hours=8)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""


def _clean(desc):
    """去掉摘要里的 HTML 标签，保留纯文本。"""
    desc = re.sub(r"<[^>]+>", " ", desc or "")
    return re.sub(r"\s+", " ", desc).strip()


def _parse_rss(xml_text, name):
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = _clean(item.findtext("description") or "")
        pubdate = (item.findtext("pubDate") or "").strip()
        if not title or not link:
            continue
        items.append({
            "source": name,
            "category": "论坛讨论",
            "title": title,
            "url": link,
            "date": _parse_date(pubdate),
            "content": desc,
            "id": make_id(link),
        })
    return items


def fetch_list():
    """返回两个板块的最新帖子列表（含 RSS 摘要），字段同其它源。"""
    items = []
    for board in BOARDS:
        try:
            xml_text = _get_rss(board["fid"])
            items.extend(_parse_rss(xml_text, board["name"]))
        except Exception as e:
            print(f"  论坛「{board['name']}」抓取失败: {e}")
    return items


def fetch_detail(url):
    """论坛正文需登录，RSS 已含摘要，故不再抓详情页。返回空串以保留摘要。"""
    return ""


# ---------------------------------------------------------------------------
# 列表页全量抓取（游客可访问，用于突破 RSS 仅 20~30 条的窗口限制）
# 列表页：forum-{fid}-{page}.html
# 每页约 85~86 帖，含标题 / 链接 / 作者 / 发帖日期 / 回复数 / 查看数
# ---------------------------------------------------------------------------
import requests  # noqa: E402  (模块内局部使用，避免影响纯 RSS 场景)


def _norm_date(s):
    """'2019-8-12' -> '2019-08-12'；无法识别时原样返回。"""
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", (s or "").strip())
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return (s or "").strip()


def _get_forum_html(fid, page, retry=3):
    url = f"https://bbs.esnai.cn/forum-{fid}-{page}.html"
    last = None
    for attempt in range(retry):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=25)
            resp.encoding = "gbk"
            return resp.text
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise last


def _extract_date(td_html):
    """从 <td class="by"> 中提取日期。

    该单元格可能是 ① 绝对日期 <em><span>2019-8-12</span></em>，
    也可能是 ② 相对时间 <em><span><span title="2026-9-29">5 天前</span></span></em>。
    优先取 title 属性里的真实日期，回退取文本（仅当文本本身是日期）。
    """
    em = re.search(r"<em>(.*?)</em>", td_html, re.S)
    if not em:
        return ""
    seg = em.group(1)
    tm = re.search(r'title="(\d{4}-\d{1,2}-\d{1,2})', seg)
    if tm:
        return _norm_date(tm.group(1))
    txt = re.sub(r"<[^>]+>", "", seg).strip()
    m = re.match(r"(\d{4}-\d{1,2}-\d{1,2})", txt)
    if m:
        return _norm_date(m.group(1))
    return ""  # "5 天前" 等无法解析时留空


def _parse_list_page(html, name):
    """解析一页列表，返回帖子条目（跳过置顶帖）。"""
    items = []
    for m in re.finditer(
        r'<tbody[^>]*id="(normal|stick)thread_(\d+)"[^>]*>(.*?)</tbody>',
        html, re.S,
    ):
        kind, tid, body = m.group(1), m.group(2), m.group(3)
        if kind != "normal":  # 置顶帖不计入正文统计
            continue
        tm = re.search(r'class="s xst"[^>]*>(.*?)</a>', body, re.S)
        if not tm:
            continue
        title = re.sub(r"<[^>]+>", "", tm.group(1)).strip()
        if not title:
            continue
        url = f"https://bbs.esnai.cn/thread-{tid}-1-1.html"

        bys = re.findall(r'<td class="by">(.*?)</td>', body, re.S)
        author, date, last_reply = "", "", ""
        if bys:
            am = re.search(r"<cite>\s*<a[^>]*>([^<]+)</a>", bys[0])
            if am:
                author = am.group(1).strip()
            date = _extract_date(bys[0])
        if len(bys) > 1:
            lm = re.search(r"<em>(.*?)</em>", bys[1], re.S)
            if lm:
                last_reply = re.sub(r"<[^>]+>", "", lm.group(1)).strip()

        nm = re.search(r'<td class="num"><a[^>]*>(\d+)</a><em>(\d+)</em>', body)
        replies = nm.group(1) if nm else ""
        views = nm.group(2) if nm else ""

        items.append({
            "source": name,
            "category": "论坛讨论",
            "title": title,
            "url": url,
            "date": date,
            "id": make_id(url),
            "content": "",
            "author": author,
            "replies": replies,
            "views": views,
            "last_reply": last_reply,
        })
    return items


def _max_page(html, fid):
    nums = re.findall(rf"forum-{fid}-(\d+)\.html", html)
    return max((int(n) for n in nums), default=1)


def fetch_board_pages(fid, name, max_pages=None, progress=None):
    """抓取某板块全部列表页。max_pages 限制页数（None=全部）。"""
    first_html = _get_forum_html(fid, 1)
    real_total = _max_page(first_html, fid)
    total_pages = min(real_total, max_pages) if max_pages else real_total

    items = _parse_list_page(first_html, name)
    for p in range(2, total_pages + 1):
        try:
            html = _get_forum_html(fid, p)
            items.extend(_parse_list_page(html, name))
        except Exception as e:
            print(f"  「{name}」第 {p} 页失败: {e}")
        if progress:
            progress(name, p, total_pages, len(items))
        time.sleep(0.25)
    return items, real_total
