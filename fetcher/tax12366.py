# -*- coding: utf-8 -*-
"""国家税务总局 12366 纳税服务平台「网上留言」栏目抓取。

API: GET /nszx/onlinemessage/messagelist?currentPage=N&pageSize=8
- pageSize 被服务器固定为 8，无论传多少
- 返回 JSON：maxCount（总留言数）、maxPage（总页数）、pageSet（当页条目）
- 字段：code(唯一id)、title(类别)、content(完整留言+答复)、
        unitname(纳税人所属地)、fbsj(发布日期, YYYY-MM-DD)
- 单条 API 不存在，content 已在 list 接口返回
"""
import time

import requests

from .common import HEADERS, make_id

BASE = "https://12366.chinatax.gov.cn"
API = f"{BASE}/nszx/onlinemessage/messagelist"
REFERER = f"{BASE}/nszx/onlinemessage/main"
PAGE_SIZE = 8  # 服务器固定
DEFAULT_PAGES = 5  # 滚动窗口：只抓最近 5 页 = 40 条，保持最新


# 缓存：fetch_list 写入，fetch_detail 读取（list 已含正文，无需二次请求）
_CONTENT_CACHE = {}


def _headers():
    h = dict(HEADERS)
    h["Referer"] = REFERER
    return h


def _get_page(page, retry=3):
    url = f"{API}?currentPage={page}&pageSize={PAGE_SIZE}"
    for i in range(retry):
        try:
            resp = requests.get(url, headers=_headers(), timeout=20)
            return resp.json()
        except Exception as e:
            if i == retry - 1:
                raise
            time.sleep(1 * (i + 1))


def fetch_list(max_pages=None):
    """抓列表分页，返回 (items, total)。

    items 字段：source / category / title / url / date / id / content
    （content 是留言完整内容，list 接口已返回，无需另抓详情页）。
    """
    if max_pages is None:
        max_pages = DEFAULT_PAGES

    first = _get_page(1)
    total = int(first.get("maxCount", 0))
    total_pages = int(first.get("maxPage", 1))
    pages_to_fetch = min(max_pages, total_pages)

    items = []
    _CONTENT_CACHE.clear()
    for p in range(1, pages_to_fetch + 1):
        if p == 1:
            data = first
        else:
            data = _get_page(p)
            time.sleep(0.3)
        for it in data.get("pageSet", []):
            code = it.get("code") or it.get("id") or ""
            if not code:
                continue
            url = f"{BASE}/nszx/onlinemessage/detail?code={code}"
            content = (it.get("content") or "").strip()
            items.append({
                "source": "12366纳税咨询",
                "category": "留言咨询",
                "title": it.get("title") or "留言咨询",
                "url": url,
                "date": it.get("fbsj") or "",
                "id": make_id(url),
                "content": content,
            })
            _CONTENT_CACHE[url] = content
    return items, total


def fetch_detail(url):
    """返回留言完整内容（已在 fetch_list 缓存，无缓存时返回空串）。"""
    return _CONTENT_CACHE.get(url, "")
