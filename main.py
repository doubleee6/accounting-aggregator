# -*- coding: utf-8 -*-
"""抓取入口：抓两站列表 + 去重 + 抓取全部新增正文 + 落盘 JSON。

设计为可在 GitHub Actions 中定时运行：
- 持久化去重：读 data/items.json 已有 id，跳过已抓取条目。
- 只对「新增」条目抓正文，避免重复请求。
- 请求间隔 + 重试，规避源站限流。
"""
import json
import os
import time

from fetcher import cicpa, esnai, chinatax

DATA_DIR = "data"
OUTPUT = os.path.join(DATA_DIR, "items.json")
REQUEST_INTERVAL = 1.5  # 每次请求间隔（秒）
MAX_RETRY = 2           # 单条正文最大重试次数


def load_existing_ids():
    if not os.path.exists(OUTPUT):
        return set()
    with open(OUTPUT, "r", encoding="utf-8") as f:
        return {it["id"] for it in json.load(f)}


def fetch_detail_with_retry(fetcher, url):
    for attempt in range(MAX_RETRY + 1):
        try:
            return fetcher(url)
        except Exception as e:
            if attempt < MAX_RETRY:
                time.sleep(2 * (attempt + 1))
                continue
            print(f"  正文抓取失败（重试 {MAX_RETRY} 次后放弃）: {url} -> {e}")
            return ""
    return ""


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    existing_ids = load_existing_ids()

    # 1. 抓三站列表并合并
    cicpa_list = cicpa.fetch_list()
    esnai_list = esnai.fetch_list()
    tax_list = chinatax.fetch_list()
    raw = cicpa_list + esnai_list + tax_list
    print(f"抓取原始条目：中注协 {len(cicpa_list)} 条，会计视野 {len(esnai_list)} 条，国家税务局 {len(tax_list)} 条")

    # 2. 内存去重（URL md5 唯一键）
    seen, merged = set(), []
    for it in raw:
        if it["id"] in seen:
            continue
        seen.add(it["id"])
        merged.append(it)

    # 3. 区分新增 / 已存在
    new_items = [it for it in merged if it["id"] not in existing_ids]
    print(f"去重后 {len(merged)} 条；本次新增 {len(new_items)} 条，已存在 {len(merged) - len(new_items)} 条")

    # 4. 对所有新增条目抓正文
    detail_fetchers = {
        "国家税务局": chinatax.fetch_detail,
        "中注协": cicpa.fetch_detail,
        "会计视野": esnai.fetch_detail,
    }
    for i, it in enumerate(new_items, 1):
        fetcher = detail_fetchers.get(it["source"], esnai.fetch_detail)
        it["content"] = fetch_detail_with_retry(fetcher, it["url"])
        print(f"  [{i}/{len(new_items)}] [{it['source']}] {it['title'][:30]}... ({len(it['content'])} 字)")
        time.sleep(REQUEST_INTERVAL)

    # 5. 合并旧数据 + 新数据，落盘
    if os.path.exists(OUTPUT):
        with open(OUTPUT, "r", encoding="utf-8") as f:
            old = json.load(f)
    else:
        old = []
    combined = old + new_items
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    print(f"\n已保存到 {OUTPUT}，累计 {len(combined)} 条")


if __name__ == "__main__":
    main()
