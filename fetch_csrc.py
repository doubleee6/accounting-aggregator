# -*- coding: utf-8 -*-
"""证监会行政处罚决定书独立爬虫：抓列表分页 + 详情正文，输出 JSON + CSV。

用法：
    python fetch_csrc.py                 # 抓全部（约 2035 条）
    python fetch_csrc.py --limit 20      # 只抓最近 20 条
    python fetch_csrc.py --pages 3       # 只抓前 3 页（30 条）

输出：
    data/csrc_penalty.json  结构化全字段
    data/csrc_penalty.csv   标题/文号/发布日期/URL/正文

支持断点续传：已抓取过的 URL（按 id 去重）会跳过。
"""
import argparse
import csv
import json
import os
import sys
import time

from fetcher import csrc

DATA_DIR = "data"
JSON_OUT = os.path.join(DATA_DIR, "csrc_penalty.json")
CSV_OUT = os.path.join(DATA_DIR, "csrc_penalty.csv")
REQUEST_INTERVAL = 0.3
MAX_RETRY = 2


def load_existing():
    """读已抓数据，返回 {id: item}。"""
    if not os.path.exists(JSON_OUT):
        return {}
    with open(JSON_OUT, "r", encoding="utf-8") as f:
        return {it["id"]: it for it in json.load(f)}


def save_json(items):
    items.sort(key=lambda x: x.get("date", ""), reverse=True)
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def save_csv(items):
    items.sort(key=lambda x: x.get("date", ""), reverse=True)
    with open(CSV_OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["标题", "文号", "发布日期", "URL", "正文"])
        for it in items:
            w.writerow([it["title"], it["doc_no"], it["date"], it["url"], it["content"]])


def fetch_detail_with_retry(url, list_title):
    for attempt in range(MAX_RETRY + 1):
        try:
            return csrc.fetch_detail(url, list_title=list_title)
        except Exception as e:
            if attempt == MAX_RETRY:
                print(f"  正文抓取失败（放弃）: {url} -> {e}")
                return {"title": list_title, "doc_no": "", "content": ""}
            time.sleep(2 * (attempt + 1))
    return {"title": list_title, "doc_no": "", "content": ""}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="最多抓取条数")
    parser.add_argument("--pages", type=int, default=None, help="最多抓取页数（每页10条）")
    args = parser.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    existing = load_existing()

    print("抓取列表…")
    items, total = csrc.fetch_list(max_pages=args.pages)
    print(f"列表共 {total} 条，本次取 {len(items)} 条（已抓 {len(existing)} 条）")

    if args.limit is not None:
        items = items[: args.limit]

    to_fetch = [it for it in items if it["id"] not in existing]
    print(f"待抓正文：{len(to_fetch)} 条")

    for i, it in enumerate(to_fetch, 1):
        info = fetch_detail_with_retry(it["url"], it["title"])
        it["title"] = info["title"]
        it["doc_no"] = info["doc_no"]
        it["content"] = info["content"]
        existing[it["id"]] = it
        print(f"  [{i}/{len(to_fetch)}] {it['doc_no'] or '无文号'} | {it['title'][:40]}")
        time.sleep(REQUEST_INTERVAL)
        # 每 50 条落盘一次，避免中断丢数据
        if i % 50 == 0:
            save_json(list(existing.values()))
            print(f"  已暂存 {len(existing)} 条")

    all_items = list(existing.values())
    save_json(all_items)
    save_csv(all_items)
    print(f"\n完成：共 {len(all_items)} 条。")
    print(f"  JSON -> {JSON_OUT}")
    print(f"  CSV  -> {CSV_OUT}")


if __name__ == "__main__":
    main()
