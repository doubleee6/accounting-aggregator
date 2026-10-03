# -*- coding: utf-8 -*-
"""12366 纳税咨询全量回填：从第 1 页扫到 maxPage（约 4801 页 / 38402 条）。

- 公开 JSON 接口，无需登录
- 断点续抓：每 200 页落盘一次，中断后重跑自动跳过已完成部分
- 输出：data/raw/tax12366_all.json
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) or ".")

# 禁用代理，避免环境变量里的代理干扰直连
for _k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(_k, None)

import requests  # noqa: E402

from fetcher.common import HEADERS, make_id  # noqa: E402

BASE = "https://12366.chinatax.gov.cn"
API = f"{BASE}/nszx/onlinemessage/messagelist"
OUT = "data/raw/tax12366_all.json"
PAGE_SIZE = 8
INTERVAL = 0.22


def get_page(page, retry=4):
    url = f"{API}?currentPage={page}&pageSize={PAGE_SIZE}"
    h = dict(HEADERS)
    h["Referer"] = f"{BASE}/nszx/onlinemessage/main"
    for i in range(retry):
        try:
            return requests.get(url, headers=h, timeout=20).json()
        except Exception:
            if i == retry - 1:
                raise
            time.sleep(1.5 * (i + 1))


def main():
    os.makedirs("data/raw", exist_ok=True)
    store = {}
    if os.path.exists(OUT):
        for it in json.load(open(OUT, encoding="utf-8")):
            store[it["id"]] = it
        print(f"断点续抓：已有 {len(store)} 条", flush=True)

    first = get_page(1)
    total_pages = int(first.get("maxPage", 1))
    total = int(first.get("maxCount", 0))
    print(f"总量：{total} 条 / {total_pages} 页", flush=True)

    for p in range(1, total_pages + 1):
        try:
            data = first if p == 1 else get_page(p)
        except Exception as e:
            print(f"  第{p}页失败: {e}", flush=True)
            continue
        for it in data.get("pageSet", []):
            code = it.get("code") or it.get("id") or ""
            if not code:
                continue
            url = f"{BASE}/nszx/onlinemessage/detail?id={code}"
            store[make_id(url)] = {
                "source": "12366纳税咨询",
                "category": "留言咨询",
                "title": (it.get("title") or "留言咨询").strip(),
                "url": url,
                "date": it.get("fbsj") or "",
                "id": make_id(url),
                "content": (it.get("content") or "").strip(),
                "region": (it.get("unitname") or "").strip(),
            }
        if p % 200 == 0 or p == total_pages:
            json.dump(list(store.values()), open(OUT, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            print(f"  [{p}/{total_pages}] 累计 {len(store)} 条", flush=True)
        if p > 1:
            time.sleep(INTERVAL)

    json.dump(list(store.values()), open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"完成：共 {len(store)} 条 -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
