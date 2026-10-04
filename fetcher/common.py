# -*- coding: utf-8 -*-
"""抓取通用工具：请求 + 去重键 + HTML 正文提取。"""
import hashlib
import re

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 视为「段落级」的标签：段内不再硬换行，段落之间用空行分隔
BLOCK_TAGS = ("h1", "h2", "h3", "h4", "h5", "p", "li", "blockquote", "td")


def get(url):
    """返回 (响应文本, 状态码)，自动探测编码。"""
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text, resp.status_code


def make_id(url):
    """用 URL 的 md5 作为稳定唯一键，用于去重。"""
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def norm_inline(s):
    """压缩段内空白：全角空格/不换行空格→普通空格，去中文之间的对齐空格。"""
    s = s.replace("\r", "").replace("\n", "")
    s = re.sub(r"[\u00a0\u3000\t ]+", " ", s)
    # 去掉「非 ASCII 字符之间」的空格：源站常用空格做对齐（如「当 事 人：」）
    s = re.sub(r"(?<=[^\x00-\x7F]) (?=[^\x00-\x7F])", "", s)
    # 去掉「数字与汉字之间」的空格：源站用 &nbsp; 做排版（如「〔2026〕319 号」）
    s = re.sub(r"(?<=\d) (?=[^\x00-\x7F])", "", s)
    s = re.sub(r"(?<=[^\x00-\x7F]) (?=\d)", "", s)
    return s.strip()


def html_to_text(node, skip_first_if=None):
    """把正文容器转成排版良好的纯文本。

    源站正文常把一句话拆进几十个 <span>/<font>，若用 get_text("\\n") 会把
    「2026」拆成「202\\n6」。这里改为：**按段落级标签切分**，段内不硬换行。
    """
    for t in node(["style", "script"]):
        t.decompose()

    blocks = []
    for el in node.find_all(BLOCK_TAGS):
        # 只取最外层段落级标签，避免嵌套时重复输出
        if el.find_parent(BLOCK_TAGS):
            continue
        txt = norm_inline(el.get_text())
        if txt:
            blocks.append(txt)

    if not blocks:
        txt = norm_inline(node.get_text())
        if txt:
            blocks.append(txt)

    # 去掉与标题重复的首段（页面标题已在卡片上展示）
    if skip_first_if and blocks:
        first = blocks[0].replace(" ", "")
        key = re.sub(r"\s+", "", skip_first_if)
        if key and (first.startswith(key) or key.startswith(first)):
            blocks.pop(0)

    return "\n\n".join(blocks)
