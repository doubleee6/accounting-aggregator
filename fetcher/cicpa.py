# -*- coding: utf-8 -*-
"""中注协「执业质量检查通告」抓取。"""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import get, make_id

BASE = "https://www.cicpa.org.cn"
LIST_URL = "https://www.cicpa.org.cn/xxcx/kjsswszyzljc"


def _date_from_url(url):
    m = re.search(r"t(\d{4})(\d{2})(\d{2})_", url)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ""


def fetch_list():
    """返回公告列表（不含正文），字段：source/category/title/url/date/id。"""
    html, _ = get(LIST_URL)
    soup = BeautifulSoup(html, "lxml")
    items = []
    ul = soup.find("ul", id="sub")
    if not ul:
        return items
    for a in ul.find_all("a"):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not title or not href:
            continue
        url = urljoin(LIST_URL + "/", href)
        items.append({
            "source": "中注协",
            "category": "处罚案例",
            "title": title,
            "url": url,
            "date": _date_from_url(url),
            "id": make_id(url),
        })
    return items


def fetch_detail(url):
    """抓取正文，优先 TRS_Editor，回退 content。"""
    html, _ = get(url)
    soup = BeautifulSoup(html, "lxml")
    node = soup.select_one("div.TRS_Editor") or soup.select_one("div.content")
    return node.get_text("\n", strip=True) if node else ""
