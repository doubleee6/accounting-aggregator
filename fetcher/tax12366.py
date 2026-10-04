# -*- coding: utf-8 -*-
"""国家税务总局 12366 纳税服务平台「网上留言」栏目抓取。

API: GET /nszx/onlinemessage/messagelist?currentPage=N&pageSize=8
- pageSize 被服务器固定为 8，无论传多少
- 返回 JSON：maxCount（总留言数）、maxPage（总页数）、pageSet（当页条目）
- 字段：code(唯一id)、title(类别)、content(仅「问题」，答复需抓详情页)、
        unitname(纳税人所属地)、fbsj(发布日期, YYYY-MM-DD)
- 详情页 detail?id=<code> 含「问题内容/答复内容/答复机构/答复时间」四段（见 fetch_detail）
"""
import html
import re
import time

import requests

from .common import HEADERS, make_id

BASE = "https://12366.chinatax.gov.cn"
API = f"{BASE}/nszx/onlinemessage/messagelist"
REFERER = f"{BASE}/nszx/onlinemessage/main"
PAGE_SIZE = 8  # 服务器固定
DEFAULT_PAGES = 30  # 每日扫描最近 30 页 = 240 条候选：新出现条目累积入库（历史保留不删）


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
            # 注意：官网详情页参数是 id 而不是 code（code 传入时服务端只返回空壳页面）
            url = f"{BASE}/nszx/onlinemessage/detail?id={code}"
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


def _field(block, label):
    """从 <th>label</th> 所在行取 textarea 内容或 input 的 value。"""
    i = block.find(label + "</th>")
    if i < 0:
        return ""
    j = block.find("</tr>", i)
    seg = block[i:j] if j > i else block[i:i + 4000]
    m = re.search(r"<textarea[^>]*>(.*?)</textarea>", seg, re.S)
    if m:
        return html.unescape(m.group(1)).strip()
    m = re.search(r'value="([^"]*)"', seg)
    if m:
        return html.unescape(m.group(1)).strip()
    return ""


def fetch_detail(url):
    """抓详情页，返回「问题 + 答复 + 答复机构/时间」的完整问答正文。

    列表接口只提供「问题」，答复仅在详情页，因此新增条目需调用本函数。
    失败时退回列表缓存内容（仅有问题），保证不产生空正文。
    """
    last = None
    for attempt in range(3):
        try:
            r = requests.get(url, headers=_headers(), timeout=25)
            if r.status_code == 200 and "答复内容" in r.text:
                h = r.text
                q = _field(h, "问题内容")
                a = _field(h, "答复内容")
                org = _field(h, "答复机构")
                date = _field(h, "答复时间")
                parts = []
                if q:
                    parts.append("【问题】\n" + q)
                if a:
                    parts.append("【答复】\n" + a)
                meta = []
                if org:
                    meta.append("答复机构：" + org)
                if date:
                    meta.append("答复时间：" + date)
                if meta:
                    parts.append("　".join(meta))
                if parts:
                    return "\n\n".join(parts)
            last = f"HTTP {r.status_code}"
        except Exception as e:
            last = type(e).__name__
        time.sleep(1.5 * (attempt + 1))
    if last:
        print(f"  12366 详情抓取失败: {url} -> {last}")
    return _CONTENT_CACHE.get(url, "")
