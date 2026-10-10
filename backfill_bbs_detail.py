# -*- coding: utf-8 -*-
"""论坛正文全量抓取（含全部回帖，支持断点续抓）。

用法：
    python backfill_bbs_detail.py              # 全量（断点续抓）
    python backfill_bbs_detail.py --limit 100  # 只抓 100 条（试跑）
    python backfill_bbs_detail.py --board cpa  # 只抓 CPA 业务探讨

产物：
    data/raw/bbs_detail.json     {帖子url: 正文}（增量写入，可反复续跑）
    data/raw/bbs_detail_state.json  抓取状态（已完成 url 集合 + 统计）

设计要点：
- 断点续抓：已完成 url 记入 state，重跑自动跳过，中断不丢进度。
- 限速 1.2s/条，遇登录失效立即停止（避免白跑）。
- 每 200 条落盘一次，进度写入 state。
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

for _k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(_k, None)

from fetcher import bbs_auth  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(RAW, "bbs_detail.json")
STATE = os.path.join(RAW, "bbs_detail_state.json")

INTERVAL = 1.2      # 每条间隔（秒）
FLUSH_EVERY = 200   # 每多少条落盘

BOARDS = [
    ("cpa", "bbs_cpa", "CPA业务探讨", 7),
    ("audit", "bbs_audit", "内部审计", 5),
]


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def save_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)   # 原子替换，避免写一半崩溃损坏文件


def load_targets(src_key, limit=None):
    """从索引取目标帖子（[id, fid, date, title, url]）。"""
    path = os.path.join(ROOT, "data", "idx", f"{src_key}.json")
    with open(path, "r", encoding="utf-8") as f:
        rows = json.load(f)
    out = []
    for row in rows:
        if len(row) >= 5 and isinstance(row[4], str) and "thread-" in row[4]:
            out.append({"id": row[0], "date": row[2], "title": row[3], "url": row[4]})
    if limit:
        out = out[:limit]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="每个版块最多抓多少条")
    ap.add_argument("--board", default=None, help="只抓指定版块：cpa / audit")
    args = ap.parse_args()

    if not bbs_auth.load_cookie():
        print("✗ 未配置 Cookie（.bbs_cookie 或环境变量 BBS_COOKIE）。")
        return 1

    detail = load_json(OUT, {})       # url -> content
    state = load_json(STATE, {"done": [], "failed": [], "stats": {}})
    done = set(state.get("done", []))
    failed = set(state.get("failed", []))

    boards = [b for b in BOARDS if (not args.board or b[0] == args.board)]
    tasks = []
    for key, src_key, name, fid in boards:
        targets = load_targets(src_key, args.limit)
        todo = [t for t in targets if t["url"] not in done]
        print(f"「{name}」索引 {len(targets)} 条，已完成 {len(targets)-len(todo)}，待抓 {len(todo)}")
        tasks.extend([(name, t) for t in todo])

    total = len(tasks)
    print(f"\n合计待抓 {total} 条，限速 {INTERVAL}s/条，"
          f"预计 {total*INTERVAL/3600:.1f} 小时\n")
    if not total:
        print("无待抓任务。")
        return 0

    s = bbs_auth._session()
    t0 = time.time()
    ok = empty = err = 0
    chars_total = 0
    auth_fail_streak = 0

    for i, (name, t) in enumerate(tasks, 1):
        try:
            content, _title, nrep = bbs_auth.fetch_thread_full(t["url"], session=s)
            e = ""
        except Exception as ex:
            content, nrep, e = "", 0, str(ex)[:100]

        if e:
            err += 1
            failed.add(t["url"])
            auth_fail_streak = 0
        elif content and len(content) > 40:
            ok += 1
            chars_total += len(content)
            detail[t["url"]] = content
            done.add(t["url"])
            failed.discard(t["url"])
            auth_fail_streak = 0
        else:
            empty += 1
            done.add(t["url"])      # 空内容也记完成，避免反复重试
            auth_fail_streak += 1
            # 连续多条空 → 极可能是登录失效，立即停
            if auth_fail_streak >= 15:
                print("\n⚠️ 连续 15 条抓不到正文，疑似登录态失效，停止抓取。")
                break

        # 进度输出（每 20 条一条日志，避免刷屏）
        if i % 20 == 0 or i == total:
            el = time.time() - t0
            speed = i / el if el else 0
            eta = (total - i) / speed / 3600 if speed else 0
            print(f"[{i:>6}/{total}] OK {ok} 空 {empty} 错 {err} | "
                  f"{chars_total/10000:.0f}万字 | {speed:.2f}条/s | 剩余 {eta:.1f}h", flush=True)

        # 定期落盘
        if i % FLUSH_EVERY == 0:
            save_json(OUT, detail)
            state.update({
                "done": sorted(done), "failed": sorted(failed),
                "stats": {"ok": ok, "empty": empty, "err": err,
                          "chars": chars_total,
                          "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
            })
            save_json(STATE, state)

        time.sleep(INTERVAL)

    save_json(OUT, detail)
    state.update({
        "done": sorted(done), "failed": sorted(failed),
        "stats": {"ok": ok, "empty": empty, "err": err, "chars": chars_total,
                  "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
    })
    save_json(STATE, state)

    el = time.time() - t0
    print(f"\n{'='*60}")
    print(f"本轮完成 | 成功 {ok} | 空内容 {empty} | 报错 {err}")
    print(f"正文合计 {chars_total/10000:.0f} 万字 | 耗时 {el/3600:.2f} 小时")
    print(f"正文库累计 {len(detail)} 条 -> {OUT}")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
