# -*- coding: utf-8 -*-
"""国家税务总局「留言公开」抓取（纳税人提问 + 官方答复）。"""
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import get, make_id

BASE = "https://www.chinatax.gov.cn"
LIST_URL = "https://www.chinatax.gov.cn/chinatax/n810356/n3255681/common_listwyc.html"


def fetch_list():
    """返回留言列表（不含正文），字段：source/category/title/url/date/id。"""
    html, _ = get(LIST_URL)
    soup = BeautifulSoup(html, "lxml")
    items = []
    box = soup.select_one("div.pagelist") or soup.select_one("div.infolist")
    if not box:
        return items
    for li in box.find_all("li"):
        a = li.find("a")
        if not a:
            continue
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not title or "content.html" not in href:
            continue
        url = urljoin(BASE, href)
        time_span = li.find("span", class_="time")
        date = time_span.get_text(strip=True) if time_span else ""
        items.append({
            "source": "国家税务局",
            "category": "留言咨询",
            "title": title,
            "url": url,
            "date": date,
            "id": make_id(url),
        })
    return items


def fetch_detail(url):
    """抓取正文：优先 div#zoomcon，回退 div.article-content。"""
    html, _ = get(url)
    soup = BeautifulSoup(html, "lxml")
    node = soup.select_one("div#zoomcon") or soup.select_one("div.article-content")
    return node.get_text("\n", strip=True) if node else ""
