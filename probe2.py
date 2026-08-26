# -*- coding: utf-8 -*-
"""精细探测：列表项容器结构 + 详情页正文结构。"""
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def get(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.encoding = r.apparent_encoding or "utf-8"
    return BeautifulSoup(r.text, "lxml")


print("### 中注协列表页：第一个通告链接的父容器结构")
soup = get("https://www.cicpa.org.cn/xxcx/kjsswszyzljc")
a = soup.find("a", href=lambda h: h and "t20250701_65502" in h)
for i, p in enumerate(a.parents):
    print(f"  parent[{i}] <{p.name}> class={p.get('class')} id={p.get('id')}")
    if i >= 3:
        break

print()
print("### 中注协详情页正文结构（第二十四号）")
soup2 = get("https://www.cicpa.org.cn/xxfb/tzgg/202507/t20250701_65502.html")
title = soup2.find("title")
print("  <title>:", title.get_text(strip=True) if title else None)
# 找正文容器：常见的正文标签
for sel in ["div.TRS_Editor", "div.content", "div.article", "div#zoom", "td.t_f", "div.main"]:
    node = soup2.select_one(sel)
    if node:
        txt = node.get_text(" ", strip=True)
        print(f"  [{sel}] 命中, 长度={len(txt)}, 开头: {txt[:80]}")
print("  页面所有 div class 列表:", sorted({c for d in soup2.find_all('div') for c in (d.get('class') or [])})[:20])

print()
print("### 会计视野列表页：列表项容器结构")
soup3 = get("https://www.esnai.cn/47/")
a3 = soup3.find("a", href=lambda h: h and "276664" in h)
for i, p in enumerate(a3.parents):
    print(f"  parent[{i}] <{p.name}> class={p.get('class')} id={p.get('id')}")
    if i >= 3:
        break

print()
print("### 会计视野详情页正文结构")
soup4 = get("https://www.esnai.cn/2025/1021/276664.shtml")
title4 = soup4.find("title")
print("  <title>:", title4.get_text(strip=True) if title4 else None)
for sel in ["div.article-content", "div.content", "div#article_content", "div.article", "div.main", "div.txt"]:
    node = soup4.select_one(sel)
    if node:
        txt = node.get_text(" ", strip=True)
        print(f"  [{sel}] 命中, 长度={len(txt)}, 开头: {txt[:80]}")
print("  页面所有 div class 列表:", sorted({c for d in soup4.find_all('div') for c in (d.get('class') or [])})[:20])
