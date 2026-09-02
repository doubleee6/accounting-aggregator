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
