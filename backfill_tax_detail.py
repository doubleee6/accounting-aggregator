# -*- coding: utf-8 -*-
"""补抓 12366 详情页：列表接口只给「问题」，答复只在详情页。

产出 data/raw/tax12366_detail.json  {id: {q, a, org, date}}
可反复运行，自动跳过已完成的条目（断点续抓）。
"""
import html
import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from fetcher.common import HEADERS

RAW = "data/raw/tax12366_all.json"
OUT = "data/raw/tax12366_detail.json"
WORKERS = 3          # 并发不宜过高，避免对官网造成压力
TIMEOUT = 30


def field(block_html, label):
    """从 <th>label</th> 所在行取 textarea 内容或 input 的 value。"""
    i = block_html.find(label + "</th>")
    if i < 0:
        return ""
    j = block_html.find("</tr>", i)
    seg = block_html[i:j] if j > i else block_html[i:i + 4000]
    m = re.search(r"<textarea[^>]*>(.*?)</textarea>", seg, re.S)
    if m:
        return html.unescape(m.group(1)).strip()
    m = re.search(r'value="([^"]*)"', seg)
    if m:
        return html.unescape(m.group(1)).strip()
    return ""


def parse_detail(h):
    return {
        "q": field(h, "问题内容"),
        "a": field(h, "答复内容"),
        "org": field(h, "答复机构"),
        "date": field(h, "答复时间"),
    }


def fetch_one(url):
    last = None
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 200 and "答复内容" in r.text:
                return parse_detail(r.text)
            last = f"HTTP {r.status_code}"
        except Exception as e:
            last = type(e).__name__
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(last or "unknown")


def save(done, lock):
    with lock:
        json.dump(done, open(OUT, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))


def main():
    items = json.load(open(RAW, encoding="utf-8"))
    done = {}
    if os.path.exists(OUT):
        done = json.load(open(OUT, encoding="utf-8"))
    print(f"待补 {len(items)} 条，已完成 {len(done)} 条")

    todo = [it for it in items if it["id"] not in done]
    if not todo:
        print("全部完成")
        return

    lock = threading.Lock()
    counter = {"ok": 0, "fail": 0}
    t0 = time.time()

    def work(it):
        try:
            d = fetch_one(it["url"])
            with lock:
                done[it["id"]] = d
                counter["ok"] += 1
            time.sleep(0.25 + random.random() * 0.25)
        except Exception as e:
            with lock:
                counter["fail"] += 1
                if counter["fail"] <= 20:
                    print(f"  失败 {it['id'][:8]} {e}")
        n = counter["ok"] + counter["fail"]
        if n % 500 == 0:
            save(done, lock)
            el = time.time() - t0
            rate = n / el
            left = (len(todo) - n) / rate / 60 if rate else 0
            print(f"  [{n}/{len(todo)}] 成功{counter['ok']} 失败{counter['fail']} "
                  f"| {rate:.1f}条/秒 | 剩余约 {left:.0f} 分钟", flush=True)

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(work, todo))

    save(done, lock)
    print(f"完成：成功 {counter['ok']}，失败 {counter['fail']}，累计 {len(done)} 条")


if __name__ == "__main__":
    main()
