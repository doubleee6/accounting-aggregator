# -*- coding: utf-8 -*-
"""抓取通用工具：请求 + 去重键。"""
import hashlib
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def get(url):
    """返回 (响应文本, 状态码)，自动探测编码。"""
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text, resp.status_code


def make_id(url):
    """用 URL 的 md5 作为稳定唯一键，用于去重。"""
    return hashlib.md5(url.encode("utf-8")).hexdigest()
