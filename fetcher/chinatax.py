# -*- coding: utf-8 -*-
"""国家税务总局「留言公开」抓取（纳税人提问 + 官方答复）。

列表页 common_listwyc.html 只展示最新 20 条且无分页；完整历史需走
manuscriptList 接口（返回带分页的列表，容器 div.common_list）。
"""
import re
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import get, make_id

BASE = "https://www.chinatax.gov.cn"
CHANNEL = "n3255681"
PAGE_SIZE = 20
HISTORICAL_PAGES = 5  # 历史基线只抓最近 5 页（约 100 条），未来每日增量自动覆盖


def _list_url(page):
    return (
        f"https://www.chinatax.gov.cn/chinatax/manuscriptList/{CHANNEL}"
        f"?_isAgg=0&_pageSize={PAGE_SIZE}&_template=index"
        f"&_channelName=留言公开&_keyWH=wenhao&page={page}"
    )


def _parse_page(html):
    """解析单页列表（div.common_list > li），返回 items。"""
    soup = BeautifulSoup(html, "lxml")
    box = soup.select_one("div.common_list")
    if not box:
        return []
    items = []
    for li in box.find_all("li"):
        a = li.find("a")
        if not a:
            continue
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not title or "content.html" not in href:
            continue
        url = urljoin(BASE, href)
        # 统一为 https，避免与旧数据的 http 链接产生去重歧义
        if url.startswith("http://"):
            url = "https://" + url[len("http://"):]
        # 日期形如 <span>[2026-08-31]</span>
        date = ""
        span = li.find("span")
        if span:
            m = re.search(r"\[(\d{4}-\d{2}-\d{2})\]", span.get_text())
            if m:
                date = m.group(1)
        items.append({
            "source": "国家税务局",
            "category": "留言咨询",
            "title": title,
            "url": url,
            "date": date,
            "id": make_id(url),
        })
    return items


def _total_pages(html):
    """从分页区解析总页数（"共47页"）。"""
    soup = BeautifulSoup(html, "lxml")
    pn = soup.select_one("div.page_num") or soup.select_one("div.newspage")
    if pn:
        m = re.search(r"共\s*(\d+)\s*页", pn.get_text())
        if m:
            return int(m.group(1))
    return 1


def fetch_list():
    """返回最近若干页留言列表，字段：source/category/title/url/date/id。

    只抓 HISTORICAL_PAGES 页作为基线；每日运行时最新留言总在前几页，
    因此未来的新增留言会被自然覆盖到。
    """
    first_html, _ = get(_list_url(1))
    total = _total_pages(first_html)
    pages = min(total, HISTORICAL_PAGES)
    items = _parse_page(first_html)
    for p in range(2, pages + 1):
        html, _ = get(_list_url(p))
        items.extend(_parse_page(html))
        time.sleep(0.3)
    return items


def fetch_detail(url):
    """抓取正文：优先 div#zoomcon，回退 div.article-content。"""
    html, _ = get(url)
    soup = BeautifulSoup(html, "lxml")
    node = soup.select_one("div#zoomcon") or soup.select_one("div.article-content")
    return node.get_text("\n", strip=True) if node else ""
