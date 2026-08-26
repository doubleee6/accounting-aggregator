# -*- coding: utf-8 -*-
"""探测中注协和会计视野栏目页的原始 HTML 结构，用于确定解析规则。"""
import requests
import sys

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

TARGETS = {
    "中注协-执业质量检查通告": "https://www.cicpa.org.cn/xxcx/kjsswszyzljc",
    "会计视野-看点/行业": "https://www.esnai.cn/47/",
}


def probe(name, url):
    print("=" * 70)
    print(f"[{name}] {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.encoding = resp.apparent_encoding or "utf-8"
        print("status:", resp.status_code, "| len:", len(resp.text))
        html = resp.text
        # 打印所有 <a> 链接，帮助判断列表项结构
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        links = soup.find_all("a")
        print(f"总链接数: {len(links)}")
        # 只打印包含日期或数字ID特征的链接
        import re
        shown = 0
        for a in links:
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if not text or len(text) < 4:
                continue
            if re.search(r"\d{4,}", href) and shown < 25:
                print(f"  [{text[:40]}] -> {href}")
                shown += 1
        print(f"  ... (展示 {shown} 条带日期/ID的链接)")
    except Exception as e:
        print("ERROR:", repr(e))


if __name__ == "__main__":
    for n, u in TARGETS.items():
        probe(n, u)
