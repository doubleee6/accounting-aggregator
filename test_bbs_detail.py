# -*- coding: utf-8 -*-
"""论坛正文小批量试抓（验证登录态 / 反爬 / 正文质量）。

用法：
    python test_bbs_detail.py            # 默认抓 30 条（CPA 版块最新的）
    python test_bbs_detail.py 50 cpa     # 抓 50 条 CPA 版块
    python test_bbs_detail.py 30 audit   # 抓 30 条 内部审计版块

产出：
    data/raw/bbs_detail_test.json   本次试抓结果（不入库，data/raw 已被忽略）
    控制台打印统计与 3 条样例
"""
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

for _k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(_k, None)

from fetcher import bbs_auth  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "data", "raw", "bbs_detail_test.json")


def load_targets(src_key, limit):
    """从索引里取前 N 条帖子（索引为紧凑数组 [id, fid, date, title, url]）。"""
    path = os.path.join(ROOT, "data", "idx", f"bbs_{src_key}.json")
    with open(path, "r", encoding="utf-8") as f:
        rows = json.load(f)
    out = []
    for row in rows:
        if len(row) >= 5 and isinstance(row[4], str) and "thread-" in row[4]:
            out.append({"id": row[0], "date": row[2], "title": row[3], "url": row[4]})
        if len(out) >= limit:
            break
    return out


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    src_key = sys.argv[2] if len(sys.argv) > 2 else "cpa"

    ck = bbs_auth.load_cookie()
    if not ck:
        print("未配置 Cookie，先按说明提供再试。")
        return
    print(f"Cookie 长度 {len(ck)} | 目标 {limit} 条 | 版块 {src_key}")

    targets = load_targets(src_key, limit)
    print(f"取到 {len(targets)} 条目标\n")

    s = bbs_auth._session()
    results = []
    ok = empty = err = 0
    lens = []
    t0 = time.time()

    for i, t in enumerate(targets, 1):
        t1 = time.time()
        try:
            content, _ = bbs_auth.fetch_thread(t["url"], session=s)
            e = ""
        except Exception as ex:
            content, e = "", str(ex)[:80]
        dt = time.time() - t1

        if e:
            err += 1
            flag = "ERR"
        elif content and len(content) > 60:
            ok += 1
            lens.append(len(content))
            flag = "OK "
        else:
            empty += 1
            flag = "空 "

        results.append({**t, "content": content, "error": e, "cost": round(dt, 2)})
        print(f"[{i:>3}/{len(targets)}] {flag} {len(content):>5} 字 {dt:>5.2f}s  {t['title'][:36]}")
        time.sleep(1.2)

    total = time.time() - t0
    print("\n" + "=" * 60)
    print(f"样本 {len(targets)} 条 | 成功 {ok} | 无正文 {empty} | 报错 {err}")
    print(f"耗时 {total:.1f}s | 平均 {total/len(targets):.2f}s/条")
    if lens:
        print(f"正文字数：中位 {int(statistics.median(lens))} | "
              f"最短 {min(lens)} | 最长 {max(lens)} | 平均 {int(statistics.mean(lens))}")
        print(f"推算全量 52408 条：约 {52408*total/len(targets)/3600:.1f} 小时")
    print("=" * 60)

    # 打印 3 条样例
    print("\n---- 样例行 ----")
    shown = 0
    for r in results:
        if r["content"] and len(r["content"]) > 60:
            print(f"\n★ {r['title']}  [{r['date']}]")
            print(f"  {r['url']}")
            print("  " + r["content"][:300].replace("\n", "\n  "))
            shown += 1
            if shown >= 3:
                break

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(results, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n结果已存：{OUT}")


if __name__ == "__main__":
    main()
