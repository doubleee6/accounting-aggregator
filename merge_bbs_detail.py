# -*- coding: utf-8 -*-
"""把抓到的论坛正文合并回列表数据。

正文库 data/raw/bbs_detail.json 为 {url: content}；
列表 data/raw/bbs_{cpa,audit}.json 为 [{... "content": "" ...}]。
本脚本按 url 匹配，把正文填入 content 字段（原地更新，保留其它字段）。

用法：
    python merge_bbs_detail.py           # 预览（不写文件）
    python merge_bbs_detail.py --apply   # 实际写入
"""
import argparse
import json
import os
import shutil
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "data", "raw")

TARGETS = ["bbs_cpa.json", "bbs_audit.json"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="实际写入（默认仅预览）")
    args = ap.parse_args()

    detail = json.load(open(os.path.join(RAW, "bbs_detail.json"), encoding="utf-8"))
    print(f"正文库：{len(detail)} 条\n")

    for fn in TARGETS:
        p = os.path.join(RAW, fn)
        rows = json.load(open(p, encoding="utf-8"))
        have_urls = {r.get("url", "") for r in rows}

        # ① 已有条目：按 url 填正文
        filled = 0
        chars = 0
        for r in rows:
            txt = detail.get(r.get("url", ""), "")
            if txt and txt.strip():
                r["content"] = txt
                filled += 1
                chars += len(txt)

        # ② 补建：正文库里、但列表源没有的帖子（如 Actions 用 RSS 抓到的新帖），
        #    从索引取元数据补成完整条目，否则抓到的全文会丢失。
        src_tag = {"bbs_cpa.json": ("CPA业务探讨", 1), "bbs_audit.json": ("内部审计", 2)}[fn]
        name, si = src_tag
        idx_path = os.path.join(ROOT, "data", "idx", fn)
        added = 0
        if os.path.exists(idx_path):
            for r in json.load(open(idx_path, encoding="utf-8")):
                if len(r) < 5:
                    continue
                iid, _si, date, title, url = r[0], r[1], r[2], r[3], r[4]
                if url in have_urls:
                    continue
                txt = detail.get(url, "")
                rows.append({
                    "source": name, "category": "论坛讨论", "title": title,
                    "url": url, "date": date, "id": iid,
                    "content": txt if txt.strip() else "",
                    "author": "", "replies": "", "views": "", "last_reply": "",
                })
                have_urls.add(url)
                if txt.strip():
                    added += 1
                    chars += len(txt)

        empty_after = sum(1 for r in rows if not (r.get("content") or "").strip())
        print(f"{fn}: 共 {len(rows)} 条")
        print(f"    填入正文 {filled} 条 + 补建带正文 {added} 条 = {filled+added} 条 | {chars/10000:.0f} 万字")
        print(f"    仍有空正文 {empty_after} 条")

        if args.apply:
            bak = p + ".bak"
            if not os.path.exists(bak):
                shutil.copy2(p, bak)
                print(f"    已备份 -> {os.path.basename(bak)}")
            tmp = p + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=1)
            os.replace(tmp, p)
            print(f"    已写入 {fn}")
        print()

    if not args.apply:
        print("（预览模式，未写入。加 --apply 实际执行）")


if __name__ == "__main__":
    main()
