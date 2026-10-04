# -*- coding: utf-8 -*-
"""把各来源数据整合为前端可用的「分片」结构。

设计目标：让前端能承载 10 万+ 条数据而不卡死。
- data/idx/manifest.json    : 总量与分片清单（首屏只拿它，几 KB）
- data/idx/recent.json      : 最近 2000 条（跨来源），默认视图首屏用
- data/idx/<dir>.json       : 每个来源的完整轻量索引 [id, srcIdx, date, title, url]
- data/body/<dir>/<月>.json : 正文分片，按来源+月份切分，前端点击时按需加载
- data/body/months.json    : 每个来源有哪些月份分片（勿用 _ 前缀，会命中根目录临时文件忽略规则）

合并规则：按 id 去重；raw 全量数据覆盖旧 items.json（内容更完整）。
"""
import glob
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

SOURCES = ["12366纳税咨询", "CPA业务探讨", "内部审计", "财政部", "中注协"]
DIRNAME = {
    "12366纳税咨询": "tax12366",
    "CPA业务探讨": "bbs_cpa",
    "内部审计": "bbs_audit",
    "财政部": "mof",
    "中注协": "cicpa",
}
RAW_GLOBS = [
    "data/raw/tax12366_all.json",
    "data/raw/bbs_audit.json",
    "data/raw/bbs_cpa.json",
]
# 12366 详情补充：{id: {q, a, org, date}}，列表接口只给「问题」，答复在详情页
TAX_DETAIL = "data/raw/tax12366_detail.json"
IDX_DIR = "data/idx"
BODY_DIR = "data/body"
RECENT_N = 2000          # 首屏默认视图条数（跨来源，按日期倒序）


def load_base_from_site():
    """从已生成的 data/idx + data/body 还原完整数据（这两者是入库的持久底库）。

    因为 data/raw/ 不入库，GitHub Actions 上的仓库里没有原始抓取文件，
    每次构建必须能从 idx（元数据）与 body（正文）完整还原出全部条目。
    """
    store = {}
    if os.path.isdir(IDX_DIR):
        for name in os.listdir(IDX_DIR):
            if not name.endswith(".json") or name in ("manifest.json", "recent.json"):
                continue
            for r in json.load(open(os.path.join(IDX_DIR, name), encoding="utf-8")):
                s = SOURCES[r[1]] if 0 <= r[1] < len(SOURCES) else ""
                store[r[0]] = {"id": r[0], "source": s, "date": r[2],
                               "title": r[3], "url": r[4], "content": ""}
    if os.path.isdir(BODY_DIR):
        for d in os.listdir(BODY_DIR):
            p = os.path.join(BODY_DIR, d)
            if not os.path.isdir(p):
                continue
            for f in os.listdir(p):
                if not f.endswith(".json"):
                    continue
                for i, c in json.load(open(os.path.join(p, f), encoding="utf-8")).items():
                    if i in store:
                        store[i]["content"] = c
    return store


def load_all():
    # ① 底库：上次构建产物（idx + body），保证全量数据在 Actions 上也不丢
    store = load_base_from_site()
    # ② 增量：本次抓取结果（items.json / raw），覆盖同 id 的元数据与正文
    fresh = []
    if os.path.exists("data/items.json"):
        fresh += json.load(open("data/items.json", encoding="utf-8"))
    for f in RAW_GLOBS:
        if os.path.exists(f):
            fresh += json.load(open(f, encoding="utf-8"))
    for it in fresh:
        i = it.get("id")
        if not i:
            continue
        old = store.get(i)
        if old is None:
            store[i] = it
            continue
        for k, v in it.items():
            if v in (None, ""):
                continue
            if k == "content":
                oc = old.get("content") or ""
                # 唯一需要保护的场景：12366 每日重抓列表只含「问题」，
                # 不能让它覆盖已由详情页补抓的「问题+答复」完整问答。
                # 其它来源的正文以本次抓取为准（排版修复后会更干净）。
                if (it.get("source") == "12366纳税咨询"
                        and "【答复】" in oc and "【答复】" not in v):
                    continue
            old[k] = v
    return list(store.values())


def apply_tax_detail(items):
    """把 12366 详情页补抓的「问题+答复」合并成完整问答正文。"""
    if not os.path.exists(TAX_DETAIL):
        return 0
    det = json.load(open(TAX_DETAIL, encoding="utf-8"))
    n = 0
    for it in items:
        if it.get("source") != "12366纳税咨询":
            continue
        d = det.get(it["id"])
        if not d:
            continue
        q = (d.get("q") or "").strip() or (it.get("content") or "").strip()
        a = (d.get("a") or "").strip()
        parts = []
        if q:
            parts.append("【问题】\n" + q)
        if a:
            parts.append("【答复】\n" + a)
        meta = []
        if d.get("org"):
            meta.append("答复机构：" + d["org"])
        if d.get("date"):
            meta.append("答复时间：" + d["date"])
        if meta:
            parts.append("　".join(meta))
        if parts:
            it["content"] = "\n\n".join(parts)
            n += 1
    return n


def main():
    items = load_all()
    items = [it for it in items if it.get("title")]
    items.sort(key=lambda x: x.get("date", ""), reverse=True)
    merged = apply_tax_detail(items)
    print(f"合并 12366 问答详情 {merged} 条")

    os.makedirs(IDX_DIR, exist_ok=True)
    by_dir = defaultdict(list)          # dir -> [row, ...]（已按日期倒序）
    bodies = defaultdict(dict)          # (dir, month) -> {id: content}
    recent = []                         # 首屏跨来源最新 N 条

    for it in items:
        s = it.get("source", "")
        if s not in DIRNAME:
            continue
        d = DIRNAME[s]
        row = [it["id"], SOURCES.index(s), it.get("date", ""),
               it.get("title", ""), it.get("url", "")]
        by_dir[d].append(row)
        if len(recent) < RECENT_N:
            recent.append(row)
        c = (it.get("content") or "").strip()
        if c:
            month = (it.get("date") or "0000")[:7]
            bodies[(d, month)][it["id"]] = c

    # 各来源索引分片
    manifest_sources = []
    total = 0
    for s in SOURCES:
        d = DIRNAME[s]
        rows = by_dir.get(d, [])
        total += len(rows)
        with open(os.path.join(IDX_DIR, d + ".json"), "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))
        manifest_sources.append({"dir": d, "name": s, "count": len(rows)})

    with open(os.path.join(IDX_DIR, "recent.json"), "w", encoding="utf-8") as f:
        json.dump(recent, f, ensure_ascii=False, separators=(",", ":"))

    manifest = {
        "total": total,
        "recent": len(recent),
        "build": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M"),
        "sources": manifest_sources,
    }
    with open(os.path.join(IDX_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    # 正文分片
    meta = defaultdict(list)
    for (d, m), content in bodies.items():
        p = os.path.join(BODY_DIR, d)
        os.makedirs(p, exist_ok=True)
        with open(os.path.join(p, f"{m}.json"), "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, separators=(",", ":"))
        meta[d].append(m)
    with open(os.path.join(BODY_DIR, "months.json"), "w", encoding="utf-8") as f:
        json.dump({k: sorted(v, reverse=True) for k, v in meta.items()},
                  f, ensure_ascii=False)

    # 清理旧的单体索引（已由分片替代，避免仓库里留一份 14MB 冗余）
    old = os.path.join("data", "index.json")
    if os.path.exists(old):
        os.remove(old)

    print(f"索引总计 {total} 条 → {IDX_DIR}/ （{len(manifest_sources)} 个来源分片）")
    for m in manifest_sources:
        sz = os.path.getsize(os.path.join(IDX_DIR, m["dir"] + ".json")) / 1024
        print(f"  {m['name']:14s} {m['count']:7d} 条  {sz:8.0f} KB")
    idx_mb = sum(os.path.getsize(os.path.join(IDX_DIR, f))
                 for f in os.listdir(IDX_DIR)) / 1024 / 1024
    print(f"索引合计 {idx_mb:.1f} MB（首屏仅加载 recent.json）")
    total_bodies = sum(len(v) for v in bodies.values())
    body_mb = sum(os.path.getsize(os.path.join(BODY_DIR, d, f))
                  for d in meta for f in os.listdir(os.path.join(BODY_DIR, d))) / 1024 / 1024
    print(f"正文分片 {len(bodies)} 个文件 / {total_bodies} 条正文 / {body_mb:.1f} MB")
    for s, months in sorted(meta.items()):
        n = sum(len(bodies[(s, m)]) for m in months)
        print(f"  {s}: {len(months)} 个月片 / {n} 条正文")


if __name__ == "__main__":
    main()
