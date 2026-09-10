# -*- coding: utf-8 -*-
"""证监会「行政处罚决定」栏目抓取。

数据链路：
- 列表接口：GET /searchList/{channelid}?_isAgg=true&_isJson=true&...&page=N
  返回 JSON，含 data.total（总数）与 data.results（title/url/publishedTimeStr）。
- 详情页：/csrc/c101928/c{id}/content.shtml
  正文在 div.detail-news，文号与当事人从正文开头提取。
"""
import re
import time

import requests
from bs4 import BeautifulSoup

from .common import HEADERS, make_id

CHANNEL_ID = "17d5ff2fe43e488dba825807ae40d63f"  # 「行政处罚决定」栏目
DETAIL_PREFIX = "https://www.csrc.gov.cn"        # 详情页协议补全
PAGE_SIZE = 10


def _list_url(page):
    """列表接口 URL（page 从 1 起）。"""
    return (
        f"https://www.csrc.gov.cn/searchList/{CHANNEL_ID}"
        f"?_isAgg=true&_isJson=true&_pageSize={PAGE_SIZE}"
        f"&_template=index&_rangeTimeGte=&_channelName=&page={page}"
    )


def _get_json(url, retry=3):
    """请求 JSON 接口，带重试。"""
    for i in range(retry):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=25)
            return resp.json()
        except Exception as e:
            if i == retry - 1:
                raise
            time.sleep(2 * (i + 1))


def _total_count():
    """第一页拿总数。"""
    data = _get_json(_list_url(1))
    return int(data.get("data", {}).get("total", 0))


def _normalize_url(url):
    """补全协议相对地址 //www.csrc.gov.cn/... -> https://..."""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return "https://www.csrc.gov.cn" + url
    return url


def _clean(s):
    """清理全角空格与多余空白，用于文号等字段。"""
    return re.sub(r"\s+", "", s or "")


def _extract_doc_no(text):
    """从正文开头提取文号，如 '〔 2026 〕 42 号' -> '〔2026〕42号'。"""
    m = re.search(r"〔\s*(\d{4})\s*〕\s*(\d+)\s*号", text)
    if m:
        return f"〔{m.group(1)}〕{m.group(2)}号"
    return ""


def _extract_party(text):
    """从正文开头提取首个当事人名称。

    处理两种格式：
    - 「当事人:XXX(以下简称YY),住所:...」 -> XXX
    - 「当事人:XXX,男/女...」 -> XXX
    兼容名称本身含括号的情况，如「大华会计师事务所(特殊普通合伙)」。
    """
    m = re.search(r"当事人[:：]\s*(.*?)(?=以下简称|,|，|。)", text, re.S)
    if not m:
        return ""
    party = m.group(1).strip()
    # 「以下简称」前常紧跟一个左括号，去掉它
    party = re.sub(r"[（(]\s*$", "", party)
    return party


def _extract_content(node):
    """按段落提取正文全文，段内文字连续、段间换行。"""
    paras = node.find_all("p")
    if paras:
        return "\n".join(p.get_text(strip=True) for p in paras if p.get_text(strip=True))
    return node.get_text("\n", strip=True)


def _parse_detail_html(html, list_title="中国证券监督管理委员会行政处罚决定书"):
    """解析详情页 HTML，返回 {title, doc_no, content}。"""
    soup = BeautifulSoup(html, "lxml")
    node = soup.select_one("div.detail-news")
    content = _extract_content(node) if node else ""
    doc_no = _extract_doc_no(content)
    party = _extract_party(content)
    # 标题：优先「通用标题（当事人） 文号」，当事人缺失则回退列表标题
    if party:
        title = f"中国证券监督管理委员会行政处罚决定书（{party}）"
        if doc_no:
            title += " " + doc_no
    else:
        title = list_title
        if doc_no:
            title += " " + doc_no
    return {"title": title, "doc_no": doc_no, "content": content}


def fetch_list(max_pages=None):
    """抓取列表（含分页）。max_pages 限制页数，None 表示全量。

    返回 items：source/category/title/url/date/id/doc_no（doc_no 初始为空，
    由详情页补充）。
    """
    total = _total_count()
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    if max_pages is not None:
        total_pages = min(total_pages, max_pages)

    items = []
    for p in range(1, total_pages + 1):
        data = _get_json(_list_url(p))
        results = data.get("data", {}).get("results", [])
        for v in results:
            url = _normalize_url(v.get("url", ""))
            if not url:
                continue
            pub = v.get("publishedTimeStr", "") or ""
            date = pub[:10] if pub else ""
            items.append({
                "source": "证监会",
                "category": "行政处罚",
                "title": v.get("title") or "中国证券监督管理委员会行政处罚决定书",
                "url": url,
                "date": date,
                "id": make_id(url),
                "doc_no": "",
            })
        if p < total_pages:
            time.sleep(0.3)
    return items, total


def fetch_detail(url, list_title="中国证券监督管理委员会行政处罚决定书"):
    """抓详情页，返回 {title, doc_no, content}。"""
    resp = requests.get(url, headers=HEADERS, timeout=25)
    resp.encoding = resp.apparent_encoding or "utf-8"
    return _parse_detail_html(resp.text, list_title)
