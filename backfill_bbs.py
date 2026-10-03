# -*- coding: utf-8 -*-
"""会计视野论坛列表全量回填（游客可访问，无需登录）。

- forum-5「内部审计」约 49 页
- forum-7「CPA业务探讨」约 1000 页
- 提取：标题 / 链接 / 作者 / 发帖日期 / 回复数 / 查看数 / 最后回复时间
- 输出：data/raw/bbs_audit.json、data/raw/bbs_cpa.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) or ".")

for _k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(_k, None)

from fetcher import bbs  # noqa: E402

BOARDS = [
    (5, "内部审计", "data/raw/bbs_audit.json"),
    (7, "CPA业务探讨", "data/raw/bbs_cpa.json"),
]


def main():
    os.makedirs("data/raw", exist_ok=True)
    for fid, name, out in BOARDS:
        print(f"开始抓取「{name}」(fid={fid}) ...", flush=True)

        def prog(_n, p, tp, cnt):
            if p % 50 == 0:
                print(f"  [{p}/{tp}] 累计 {cnt} 条", flush=True)

        try:
            items, real_total = bbs.fetch_board_pages(fid, name, progress=prog)
        except Exception as e:
            print(f"「{name}」抓取失败: {e}", flush=True)
            continue
        json.dump(items, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"「{name}」完成：{len(items)} 条（真实总页数 {real_total}）-> {out}", flush=True)


if __name__ == "__main__":
    main()
