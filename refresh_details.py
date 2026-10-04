# -*- coding: utf-8 -*-
"""一次性脚本：用修正后的提取逻辑重抓「财政部 / 中注协」正文（修排版）。

原实现用 get_text("\\n") 会把每个 <span> 换行，导致「2026」被拆成「202\\n6」。
本脚本重抓并覆盖 data/items.json 中这两类来源的 content，同时落盘 data/raw/。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetcher import cicpa, mof  # noqa: E402

ITEMS = "data/items.json"
RAW_OUT = "data/raw/details_refreshed.json"
FETCHERS = {"财政部": mof.fetch_detail, "中注协": cicpa.fetch_detail}


def main():
    items = json.load(open(ITEMS, encoding="utf-8"))
    targets = [it for it in items if it.get("source") in FETCHERS]
    print(f"待重抓 {len(targets)} 条（财政部/中注协）")

    good, bad = 0, 0
    for i, it in enumerate(targets, 1):
        fn = FETCHERS[it["source"]]
        try:
            text = fn(it["url"])
        except Exception as e:
            text = ""
            print(f"  [{i}] 异常 {type(e).__name__} {it['url']}")
        if text and " " in text[:40] and len(text) < 200:
            pass
        if text:
            it["content"] = text
            good += 1
        else:
            bad += 1
            print(f"  [{i}] 空正文 {it['title'][:30]}")
        if i % 20 == 0:
            print(f"  [{i}/{len(targets)}] 成功{good} 失败{bad}", flush=True)
        time.sleep(0.4)

    json.dump(items, open(ITEMS, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump({it["id"]: it["content"] for it in targets if it.get("content")},
              open(RAW_OUT, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"完成：成功 {good}，失败 {bad}")


if __name__ == "__main__":
    main()
