# -*- coding: utf-8 -*-
"""财政部「监督评价局」行政处罚决定书抓取。"""
import re
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import get, make_id

BASE = "https://www.mof.gov.cn/gp/xxgkml/jdjcj/"


def _page_url(n):
    """第 n 页（从 0 起）：index.htm 或 index_{n}.htm。"""
    return BASE + ("index.htm" if n == 0 else f"index_{n}.htm")


def _date_fmt(text):
    """'2026年07月31日' -> '2026-07-31'。"""
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ""


def _total_pages(html):
    """从 createPageHTML(12, 0, ...) 提取总页数。"""
    m = re.search(r"createPageHTML\(\s*(\d+)\s*,", html)
    return int(m.group(1)) if m else 1


def _parse_page(html):
    """解析单页列表（table.gkml_tabfr），返回 items。"""
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("table.gkml_tabfr")
    if not table:
        return []
    items = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue  # 表头行
        a = tds[0].find("a")
        if not a:
            continue
        href = a.get("href", "")
        title = ""
        script = tds[0].find("script")
        if script:
            m = re.search(r'var str = "(.*?)";', script.get_text(), re.S)
            if m:
                title = m.group(1).strip()
        if not title:
            title = a.get_text(strip=True)
        if not title or not href:
            continue
        url = urljoin(BASE, href)
        items.append({
            "source": "财政部",
            "category": "处罚案例",
            "title": title,
            "url": url,
            "date": _date_fmt(tds[2].get_text()),
            "id": make_id(url),
        })
    return items


def fetch_list():
    """抓取全部分页（约 12 页），字段同其它源。"""
    first_html, _ = get(_page_url(0))
    total = _total_pages(first_html)
    items = _parse_page(first_html)
    for n in range(1, total):
        html, _ = get(_page_url(n))
        items.extend(_parse_page(html))
        time.sleep(0.3)
    return items


def fetch_detail(url):
    """抓取正文：div.sqxzbList2。"""
    html, _ = get(url)
    soup = BeautifulSoup(html, "lxml")
    node = soup.select_one("div.sqxzbList2")
    return node.get_text("\n", strip=True) if node else ""
