# -*- coding: utf-8 -*-
"""中国会计视野「看点/行业」抓取。"""
import re

from bs4 import BeautifulSoup

from .common import get, make_id

LIST_URL = "https://www.esnai.cn/47/"


def _date_from_url(url):
    m = re.search(r"/(\d{4})/(\d{2})(\d{2})/", url)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ""


def _abs(url):
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http"):
        return url
    return "https://www.esnai.cn" + url


def fetch_list():
    """返回列表（不含正文），字段：source/category/title/url/date/id。"""
    html, _ = get(LIST_URL)
    soup = BeautifulSoup(html, "lxml")
    items = []
    ul = soup.find("ul", class_="txt_list")
    if not ul:
        return items
    for a in ul.find_all("a"):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not title or not href:
            continue
        url = _abs(href)
        items.append({
            "source": "会计视野",
            "category": "处罚案例",
            "title": title,
            "url": url,
            "date": _date_from_url(url),
            "id": make_id(url),
        })
    return items


def fetch_detail(url):
    """抓取正文，多选择器容错。"""
    html, _ = get(url)
    soup = BeautifulSoup(html, "lxml")
    for sel in ("div#endtext", "div#article_content", "div.content"):
        node = soup.select_one(sel)
        if node and len(node.get_text(strip=True)) > 50:
            return node.get_text("\n", strip=True)
    return ""
