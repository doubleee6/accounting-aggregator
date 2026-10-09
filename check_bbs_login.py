# -*- coding: utf-8 -*-
"""论坛登录态自检：验证 .bbs_cookie 是否有效。

用法：
    python check_bbs_login.py            # 用 data/idx 里第一条 CPA 帖子做测试
    python check_bbs_login.py <帖子URL>   # 指定帖子

输出：
    [1] Cookie 是否配置
    [2] 目标帖子是否抓到了正文（长度）
    [3] 结论：登录态有效 / 无效（游客被拒）
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetcher import bbs_auth  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))


def sample_url():
    """从索引里取一条最新的 CPA 帖子 URL 作为测试对象。"""
    p = os.path.join(ROOT, "data", "idx", "bbs_cpa.json")
    with open(p, "r", encoding="utf-8") as f:
        rows = json.load(f)
    # 紧凑数组结构： [id, fid, date, title, url]
    for row in rows:
        if len(row) >= 5 and isinstance(row[4], str) and "thread-" in row[4]:
            return row[4], row[3]
    return None, None


def main():
    ck = bbs_auth.load_cookie()
    print("[1] Cookie：", ("已配置（长度 %d）" % len(ck)) if ck else "未配置")

    url, title = (sys.argv[1], "") if len(sys.argv) > 1 else sample_url()
    if not url:
        print("找不到测试帖子")
        return
    print("    测试帖子：", url)
    if title:
        print("    标题：", title)

    if not ck:
        print("[2] 跳过抓取（没有 Cookie）")
        print("[3] 结论：登录态无效 —— 请先按说明提供 Cookie。")
        return

    s = bbs_auth._session()
    try:
        content, t = bbs_auth.fetch_thread(url, session=s)
    except Exception as e:
        print("[2] 抓取异常：", e)
        print("[3] 结论：无法确认，请检查网络后重试。")
        return

    print("[2] 抓到正文长度：", len(content or ""))
    if content and len(content) > 80:
        print("    正文开头：", content[:120].replace("\n", " "))
        print("[3] 结论：登录态有效，可以开始批量抓取。")
    else:
        print("[3] 结论：登录态无效（仍被当作游客拒之门外）—— Cookie 可能过期或不完整。")


if __name__ == "__main__":
    main()
