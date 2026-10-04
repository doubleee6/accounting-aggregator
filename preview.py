# -*- coding: utf-8 -*-
"""把 data/items.json 渲染成静态预览页（顶部官网直达 + 左导航 + 右内容）。"""
import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone

DATA = os.path.join("data", "items.json")
IDX_DIR = os.path.join("data", "idx")        # 前端使用的分片索引（由 build_site.py 生成）
OUT = "index.html"
SRC_NAMES = ["12366纳税咨询", "CPA业务探讨", "内部审计", "财政部", "中注协"]

# 顶部官网直达入口
OFFICIAL_SITES = [
    {"name": "国家税务总局", "url": "https://www.chinatax.gov.cn/"},
    {"name": "中国注册会计师协会", "url": "https://www.cicpa.org.cn/"},
    {"name": "中国会计视野", "url": "https://www.esnai.cn/"},
    {"name": "中国注册税务师协会", "url": "https://www.cctaa.cn/"},
    {"name": "财政部", "url": "https://www.mof.gov.cn/"},
    {"name": "函证导航", "url": "https://confirm.maoyanqing.com/"},
]

# 每日摘要：主题词表（会计/审计/税务常见主题）
THEMES = [
    "增值税", "企业所得税", "个人所得税", "研发费用", "加计扣除", "发票", "函证",
    "审计", "处罚", "惩戒", "税收优惠", "免税", "退税", "进项", "销项", "汇算清缴",
    "预缴", "小规模纳税人", "一般纳税人", "股份支付", "合并", "关联", "内审", "内控",
    "折旧", "存货", "减值", "股权", "重组", "亏损", "弥补", "留抵", "收入", "成本",
    "行政处罚", "严重失信", "执业质量", "非居民", "出口", "离境",
]


def summarize_day(items):
    """生成单日摘要：条数 + 来源分布 + 热点主题。"""
    n = len(items)
    by_source = Counter(it.get("source", "") for it in items)
    src_parts = "、".join(f"{k}{v}条" for k, v in by_source.most_common())
    kc = Counter()
    for it in items:
        title = it.get("title", "") or ""
        for w in THEMES:
            if w in title:
                kc[w] += 1
    hot = "、".join(w for w, _ in kc.most_common(4))
    parts = [f"共 {n} 条"]
    if src_parts:
        parts.append(src_parts)
    if hot:
        parts.append(f"热点：{hot}")
    return " · ".join(parts)


def load_items():
    """读取 build_site.py 生成的各来源索引分片；缺失时回退到 items.json。"""
    items = []
    skip = {"manifest.json", "recent.json"}
    if os.path.isdir(IDX_DIR):
        for name in sorted(os.listdir(IDX_DIR)):
            if not name.endswith(".json") or name in skip:
                continue
            with open(os.path.join(IDX_DIR, name), "r", encoding="utf-8") as f:
                for r in json.load(f):
                    items.append({
                        "id": r[0], "si": r[1],
                        "source": SRC_NAMES[r[1]] if 0 <= r[1] < len(SRC_NAMES) else "",
                        "date": r[2], "title": r[3], "url": r[4],
                    })
    if not items and os.path.exists(DATA):
        with open(DATA, "r", encoding="utf-8") as f:
            items = json.load(f)
    return items


def main():
    items = load_items()
    items = [it for it in items if it.get("title")]
    items.sort(key=lambda x: x.get("date", ""), reverse=True)
    counts = Counter(it.get("source", "") for it in items)
    total = len(items)

    # 数据最新日期 + 最后检查时间（北京时间，UTC+8）
    valid_dates = sorted({it.get("date") for it in items if it.get("date") and it.get("date") != "未知"})
    latest_date = valid_dates[-1] if valid_dates else "暂无数据"
    check_time = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")

    # 数据不再内嵌页面，改为前端异步加载 data/index.json（支撑十万级条目）

    # 每日摘要：最近 14 天每天一组，更早的合并为「更早」
    by_day = {}
    for it in items:
        d = it.get("date", "") or "未知"
        by_day.setdefault(d, []).append(it)
    days_sorted = sorted(by_day.keys(), reverse=True)
    recent_days = days_sorted[:14]
    old_days = days_sorted[14:]
    daily_summaries = {d: summarize_day(by_day[d]) for d in recent_days}
    if old_days:
        old_items = [it for d in old_days for it in by_day[d]]
        daily_summaries["更早"] = summarize_day(old_items)
    daily_js = json.dumps(daily_summaries, ensure_ascii=False)

    # 左侧分类导航（支持两级：中国会计视野 → CPA业务探讨/内部审计）
    GROUPS = [
        ("财政部", None),
        ("12366纳税咨询", None),
        ("中注协", None),
        ("中国会计视野", ["CPA业务探讨", "内部审计"]),
    ]
    nav = ['<div class="nav-item active" data-src="all"><span>全部</span><span class="badge">%d</span></div>' % total]
    match_map = {}
    for name, children in GROUPS:
        if children is None:
            c = counts.get(name, 0)
            match_map[name] = [name]
            nav.append(
                '<div class="nav-item" data-src="%s"><span>%s</span><span class="badge">%d</span></div>'
                % (name, name, c)
            )
        else:
            parent_c = sum(counts.get(ch, 0) for ch in children)
            match_map[name] = children
            nav.append(
                '<div class="nav-item nav-parent" data-src="%s"><span>%s</span><span class="badge">%d</span><span class="arrow">▾</span></div>'
                % (name, name, parent_c)
            )
            nav.append('<div class="nav-children">')
            for ch in children:
                c = counts.get(ch, 0)
                match_map[ch] = [ch]
                nav.append(
                    '<div class="nav-item nav-child" data-src="%s"><span>%s</span><span class="badge">%d</span></div>'
                    % (ch, ch, c)
                )
            nav.append('</div>')
    nav_html = "\n".join(nav)
    match_js = json.dumps(match_map, ensure_ascii=False)

    # 顶部官网直达（胶囊样式，无外链图标）
    sites_html = "\n".join(
        '<a class="ql" href="%s" target="_blank" rel="noopener">%s</a>'
        % (s["url"], s["name"])
        for s in OFFICIAL_SITES
    )

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>会计信息聚合工作台</title>
<link rel="icon" href="data:,">
<style>
  :root {
    --bg: #f4f5f7; --card: #ffffff; --text: #1a1d21; --muted: #8a919f;
    --primary: #0f766e; --primary-soft: #e6f4f1; --border: #e7e9ee;
    --tax: #b45309; --tax-bg: #fef3c7;
    --cicpa: #0f766e; --cicpa-bg: #ccfbf1;
    --esnai: #1d4ed8; --esnai-bg: #dbeafe;
    --cpa: #7c3aed; --cpa-bg: #ede9fe;
    --audit: #be185d; --audit-bg: #fce7f3;
    --mof: #1e40af; --mof-bg: #e0e7ff;
    --shadow-sm: 0 1px 2px rgba(16,24,40,.05);
    --shadow-md: 0 4px 14px rgba(16,24,40,.08);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg); color: var(--text); line-height: 1.6;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI",
                 "PingFang SC", "Microsoft YaHei", sans-serif;
    padding: 24px 20px 48px;
  }
  .wrap { max-width: 1040px; margin: 0 auto; }

  /* 顶栏 */
  .topbar { display: flex; align-items: center; gap: 14px; margin-bottom: 16px; }
  .logo {
    width: 44px; height: 44px; border-radius: 12px; flex-shrink: 0;
    background: var(--primary); display: flex; align-items: center; justify-content: center;
  }
  .topbar h1 { font-size: 21px; font-weight: 600; letter-spacing: -.01em; }
  .topbar p { color: var(--muted); font-size: 13px; margin-top: 2px; }
  .topbar .title { flex: 1; min-width: 0; }
  .status { flex-shrink: 0; text-align: right; }
  .status-row { display: flex; align-items: center; gap: 8px; justify-content: flex-end; font-size: 12.5px; line-height: 1.6; }
  .status-label { color: var(--muted); }
  .status-val { color: var(--primary); font-weight: 600; font-variant-numeric: tabular-nums; }
  .status-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #22c55e; margin-right: 1px; }

  /* 顶部官网直达 */
  .quick-links { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
  .ql {
    display: inline-flex; align-items: center; gap: 6px; padding: 7px 14px;
    border-radius: 999px; font-size: 13px; background: var(--card);
    border: 1px solid var(--border); color: #4b5563; text-decoration: none;
    box-shadow: var(--shadow-sm); transition: all .15s;
  }
  .ql:hover { border-color: var(--primary); color: var(--primary); background: var(--primary-soft); }
  .ql svg { color: var(--muted); flex-shrink: 0; }
  .ql:hover svg { color: var(--primary); }

  /* 搜索栏 */
  .searchbar {
    display: flex; align-items: center; gap: 10px; background: var(--card);
    border: 1px solid var(--border); border-radius: 14px; padding: 12px 16px;
    box-shadow: var(--shadow-sm); margin-bottom: 18px;
    transition: border-color .15s, box-shadow .15s;
  }
  .searchbar:focus-within { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-soft); }
  .searchbar svg { color: var(--muted); flex-shrink: 0; }
  .searchbar input { flex: 1; border: none; outline: none; font-size: 15px; background: transparent; color: var(--text); }
  .searchbar input::placeholder { color: #b0b6c0; }

  /* 主体布局 */
  .main { display: flex; gap: 18px; align-items: flex-start; }

  /* 左侧栏 */
  .sidebar { width: 210px; flex-shrink: 0; position: sticky; top: 20px; }
  .panel { background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 10px; box-shadow: var(--shadow-sm); }
  .group-title { font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; padding: 8px 10px 6px; }
  .nav-item {
    display: flex; align-items: center; gap: 8px; padding: 10px 12px; border-radius: 10px;
    cursor: pointer; font-size: 14px; color: #4b5563; transition: background .12s;
  }
  .nav-item:hover { background: #f2f4f7; }
  .nav-item.active { background: var(--primary-soft); color: var(--primary); font-weight: 500; }
  .nav-item .badge { margin-left: auto; background: #eceef1; color: #6b7280; border-radius: 10px; padding: 1px 8px; font-size: 12px; }
  .nav-item.active .badge { background: #cfe8e2; color: var(--primary); }
  .nav-item .soon { font-size: 11px; color: var(--tax); background: var(--tax-bg); border-radius: 6px; padding: 1px 6px; font-weight: 500; }
  .nav-parent .arrow { font-size: 11px; color: var(--muted); margin-left: 4px; transition: transform .15s; }
  .nav-parent.open .arrow { transform: rotate(180deg); }
  .nav-children { display: none; padding-left: 6px; margin-top: 2px; }
  .nav-children.open { display: block; }
  .nav-child { padding-left: 20px; font-size: 13px; }

  /* 右侧内容 */
  .content { flex: 1; min-width: 0; }
  .count { color: var(--muted); font-size: 13px; margin: 2px 2px 12px; }
  .card {
    background: var(--card); border: 1px solid var(--border); border-radius: 14px;
    padding: 16px 18px; margin-bottom: 12px; box-shadow: var(--shadow-sm);
    transition: box-shadow .15s, transform .15s;
  }
  .card:hover { box-shadow: var(--shadow-md); transform: translateY(-1px); }
  .card .meta { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--muted); }
  .tag { padding: 2px 9px; border-radius: 6px; font-size: 12px; font-weight: 500; }
  .tag.cicpa { background: var(--cicpa-bg); color: var(--cicpa); }
  .tag.esnai { background: var(--esnai-bg); color: var(--esnai); }
  .tag.cpa { background: var(--cpa-bg); color: var(--cpa); }
  .tag.audit { background: var(--audit-bg); color: var(--audit); }
  .tag.mof { background: var(--mof-bg); color: var(--mof); }
  .tag.tax { background: var(--tax-bg); color: var(--tax); }
  .card h2 { font-size: 16px; font-weight: 600; margin: 8px 0 6px; line-height: 1.45; }
  .card h2 a { color: var(--text); text-decoration: none; }
  .card h2 a:hover { color: var(--primary); }
  .card .sum { font-size: 13.5px; color: #5a6472; }
  .empty { text-align: center; color: var(--muted); padding: 56px 0; font-size: 14px; }
  .card.new { border-left: 3px solid #e11d48; background: linear-gradient(90deg, #fff5f6 0%, #ffffff 40%); }
  .badge-new {
    display: inline-flex; align-items: center; background: #ffe4e6; color: #e11d48;
    padding: 1px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; line-height: 1.5;
  }

  /* Tab 切换 */
  .tabs { display: flex; gap: 8px; margin-bottom: 16px; }
  .tab {
    padding: 9px 20px; border-radius: 10px; font-size: 14px; cursor: pointer;
    color: #4b5563; background: var(--card); border: 1px solid var(--border);
    transition: all .15s; font-weight: 500;
  }
  .tab:hover { border-color: var(--primary); color: var(--primary); }
  .tab.active { background: var(--primary); color: #ffffff; border-color: var(--primary); }

  /* 每日更新看板 */
  .daily-board { max-width: 760px; }
  .day-group {
    background: var(--card); border: 1px solid var(--border); border-radius: 14px;
    margin-bottom: 12px; box-shadow: var(--shadow-sm); overflow: hidden;
  }
  .day-head {
    display: flex; align-items: center; gap: 12px; padding: 14px 18px;
    cursor: pointer; user-select: none;
  }
  .day-head:hover { background: #f8fafb; }
  .day-title { font-size: 15px; font-weight: 600; white-space: nowrap; }
  .day-title .today-flag { color: #e11d48; font-weight: 700; }
  .day-summary { flex: 1; font-size: 13px; color: var(--muted); line-height: 1.5; }
  .day-arrow { color: var(--muted); transition: transform .15s; font-size: 12px; flex-shrink: 0; }
  .day-group.open .day-arrow { transform: rotate(180deg); }
  .day-body { display: none; padding: 0 18px 16px; }
  .day-group.open .day-body { display: block; }
  .d-src { margin-top: 12px; }
  .d-src-name { font-size: 12.5px; color: var(--muted); font-weight: 600; margin-bottom: 6px; }
  .d-card {
    display: flex; align-items: center; gap: 8px; padding: 8px 10px;
    border-radius: 8px; font-size: 14px; transition: background .12s;
  }
  .d-card:hover { background: #f2f4f7; }
  .d-card .tag { flex-shrink: 0; }
  .d-card a { color: var(--text); text-decoration: none; flex: 1; min-width: 0; }
  .d-card a:hover { color: var(--primary); }

  /* 站内阅读浮层 */
  .reader-mask {
    display: none; position: fixed; inset: 0; background: rgba(16,24,40,.42);
    z-index: 100; padding: 28px 16px; backdrop-filter: blur(2px);
  }
  .reader-mask.open { display: flex; align-items: flex-start; justify-content: center; }
  .reader {
    background: var(--card); border-radius: 16px; width: 100%; max-width: 760px;
    max-height: calc(100vh - 56px); display: flex; flex-direction: column;
    box-shadow: 0 20px 48px rgba(16,24,40,.22); overflow: hidden;
  }
  .reader-head {
    display: flex; align-items: center; gap: 10px; padding: 14px 18px;
    border-bottom: 1px solid var(--border); flex-shrink: 0; flex-wrap: wrap;
  }
  .reader-meta { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--muted); }
  .reader-actions { margin-left: auto; display: flex; align-items: center; gap: 8px; }
  .btn-src {
    display: inline-flex; align-items: center; gap: 4px; padding: 6px 12px; border-radius: 8px;
    font-size: 12.5px; text-decoration: none; background: var(--primary-soft);
    color: var(--primary); border: 1px solid #cfe8e2; transition: all .15s; font-weight: 500;
  }
  .btn-src:hover { background: #d8ece7; }
  .btn-close {
    width: 30px; height: 30px; border-radius: 8px; border: 1px solid var(--border);
    background: #fff; color: var(--muted); font-size: 14px; cursor: pointer; line-height: 1;
  }
  .btn-close:hover { background: #f2f4f7; color: var(--text); }
  .reader-title { font-size: 19px; font-weight: 600; line-height: 1.5; padding: 16px 22px 0; }
  .reader-body { padding: 12px 22px 24px; overflow-y: auto; flex: 1; }
  .reader-text { font-size: 15px; line-height: 1.85; color: #2b3038; white-space: pre-wrap; word-break: break-word; }
  .reader-note {
    font-size: 13px; color: var(--tax); background: var(--tax-bg); border-radius: 8px;
    padding: 10px 14px; margin-bottom: 14px; line-height: 1.6;
  }
  .card h2 a { cursor: pointer; }
  .card .meta .src-link {
    margin-left: auto; font-size: 12px; color: var(--muted); text-decoration: none;
    border-bottom: 1px dashed #cfd4dc; flex-shrink: 0;
  }
  .card .meta .src-link:hover { color: var(--primary); border-color: var(--primary); }
  .d-card a { cursor: pointer; }
  /* 「加载全部」按钮：首屏只加载最近一批，点此拉取全量索引 */
  .load-all-wrap { display: flex; justify-content: center; padding: 22px 0 6px; }
  .load-all-btn {
    padding: 10px 22px; border-radius: 999px; cursor: pointer; font-size: 13.5px;
    background: var(--card); color: var(--primary); border: 1px solid var(--primary);
    box-shadow: var(--shadow-sm); transition: all .15s;
  }
  .load-all-btn:hover { background: var(--primary-soft); }
  .load-all-btn:disabled { opacity: .6; cursor: default; }
  @media (max-width: 720px) {
    .reader-mask { padding: 0; }
    .reader { max-width: 100%; max-height: 100vh; height: 100vh; border-radius: 0; }
    .reader-body { padding: 12px 16px 24px; }
    .reader-title { padding: 14px 16px 0; font-size: 17px; }
  }

  @media (max-width: 720px) {
    .topbar { flex-wrap: wrap; }
    .status { width: 100%; text-align: left; }
    .status-row { justify-content: flex-start; }
    .main { flex-direction: column; }
    .sidebar { width: 100%; position: static; }
    .nav-items-row { display: flex; gap: 6px; overflow-x: auto; }
    .nav-item { flex-shrink: 0; }
  }
</style>
</head>
<body>
<div class="wrap">
  <header class="topbar">
    <div class="logo">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.66 3.58 3 8 3s8-1.34 8-3V5"/><path d="M4 11v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6"/></svg>
    </div>
    <div class="title">
      <h1>会计信息聚合工作台</h1>
      <p>聚合税务总局 12366 问答 · 中注协 · 中国会计视野论坛 · 财政部，共 __TOTAL__ 条</p>
    </div>
    <div class="status">
      <div class="status-row"><span class="status-label">数据更新至</span><span class="status-val">__LATEST__</span></div>
      <div class="status-row"><span class="status-label">最近检查</span><span class="status-val">__CHECK__</span><span class="status-dot"></span></div>
    </div>
  </header>

  <div class="quick-links">
__SITES__
  </div>

  <div class="tabs">
    <div class="tab active" data-tab="browse">分类浏览</div>
    <div class="tab" data-tab="daily">每日更新</div>
  </div>

  <div id="view-browse">
  <div class="searchbar">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    <input type="search" id="q" placeholder="搜索标题关键词，如：增值税 / 公开谴责 / 函证">
  </div>

  <div class="main">
    <aside class="sidebar">
      <div class="panel">
        <div class="group-title">信息分类</div>
        <div class="nav-items-row" id="sidebar">
__NAV__
        </div>
      </div>
    </aside>

    <section class="content">
      <div class="count" id="count"></div>
      <div class="list" id="list"></div>
    </section>
  </div>
  </div>

  <div id="view-daily" style="display:none">
    <div class="daily-board" id="dailyBoard"></div>
  </div>
</div>

<!-- 站内阅读浮层 -->
<div class="reader-mask" id="readerMask" onclick="closeReader()">
  <div class="reader" onclick="event.stopPropagation()">
    <div class="reader-head">
      <div class="reader-meta" id="readerMeta"></div>
      <div class="reader-actions">
        <a class="btn-src" id="readerSrc" href="#" target="_blank" rel="noopener">官网原文 ↗</a>
        <button class="btn-close" onclick="closeReader()" title="关闭 (Esc)">✕</button>
      </div>
    </div>
    <div class="reader-title" id="readerTitle"></div>
    <div class="reader-body" id="readerBody"></div>
  </div>
</div>
<script>
const MATCH = __MATCH__;
const DAILY = __DAILY__;
const list = document.getElementById('list');
const count = document.getElementById('count');
const dailyBoard = document.getElementById('dailyBoard');
let src = 'all';
let kw = '';
let DATA = [];        // 全量索引（异步加载）
let filtered = [];    // 当前筛选结果
let shown = 0;        // 已渲染条数
const PAGE = 60;      // 每批渲染条数

// 来源顺序（必须与 build_site.py 的 SOURCES/DIRNAME 一致）
const SRC_NAMES = ['12366纳税咨询', 'CPA业务探讨', '内部审计', '财政部', '中注协'];
const SRC_DIR   = ['tax12366', 'bbs_cpa', 'bbs_audit', 'mof', 'cicpa'];
const bodyCache = {};  // 正文分片缓存

function esc(s) { return (s || '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

function tagFor(si) {
  const n = SRC_NAMES[si];
  if (n === '财政部') return '<span class="tag mof">财政部</span>';
  if (n === '中注协') return '<span class="tag cicpa">中注协</span>';
  if (n === '12366纳税咨询') return '<span class="tag tax">12366纳税咨询</span>';
  if (n === 'CPA业务探讨') return '<span class="tag cpa">CPA业务探讨</span>';
  if (n === '内部审计') return '<span class="tag audit">内部审计</span>';
  return '<span class="tag esnai">会计视野</span>';
}

// 论坛类来源：正文需登录态抓取，未收录时给出提示
const SUMMARY_ONLY = {'CPA业务探讨': 1, '内部审计': 1};

// —— 索引按来源分片，按需加载（支撑十万级条目）——
const BUILD = String(Date.now());        // 版本号，避免浏览器缓存旧分片
const TOTAL = __TOTAL__;                 // 索引总条数（构建时写入）
const loadedDirs = new Set();            // 已加载的来源分片
let allLoaded = false;

function rowToObj(r) { return { id: r[0], si: r[1], date: r[2], title: r[3], url: r[4] }; }

async function fetchIdx(name) {
  try {
    const r = await fetch('data/idx/' + name + '?v=' + BUILD);
    return r.ok ? await r.json() : [];
  } catch (e) { return []; }
}

// 把新行并入 DATA（按 id 去重），保持日期倒序
function absorb(rows) {
  const have = new Set(DATA.map(x => x.id));
  let added = 0;
  for (const r of rows) {
    if (have.has(r[0])) continue;
    DATA.push(rowToObj(r)); added++;
  }
  if (added) DATA.sort((a, b) => (a.date < b.date ? 1 : (a.date > b.date ? -1 : 0)));
  return added;
}

// 载入某个来源的完整索引分片
async function ensureSource(si) {
  const dir = SRC_DIR[si];
  if (!dir || loadedDirs.has(dir)) return;
  loadedDirs.add(dir);
  absorb(await fetchIdx(dir + '.json'));
}

// 载入全部来源（“加载全部”与搜索时使用）
async function ensureAll() {
  if (allLoaded) return;
  for (let i = 0; i < SRC_NAMES.length; i++) await ensureSource(i);
  allLoaded = true;
}

function updateLoadAllBtn() {
  const b = document.getElementById('loadAll');
  if (!b) return;
  b.textContent = '当前仅加载最近 ' + DATA.length.toLocaleString() +
    ' 条 · 点击加载全部 ' + TOTAL.toLocaleString() + ' 条';
}

// 首屏：只拉 recent.json（跨来源最新 2000 条），几十 KB 即可渲染
let bodyMeta = {};   // dir -> [月份]（避免请求不存在的正文分片，减少 404）
async function loadBodyMeta() {
  try {
    const r = await fetch('data/body/months.json?v=' + BUILD);
    if (r.ok) bodyMeta = await r.json();
  } catch (e) { bodyMeta = {}; }
}

async function init() {
  const [rows] = await Promise.all([fetchIdx('recent.json'), loadBodyMeta()]);
  DATA = rows.map(rowToObj);
  render();
  renderDaily();
  openFromHash();
}

// 取正文：按「来源+月份」定位分片，懒加载并缓存
async function getBody(it) {
  const dir = SRC_DIR[it.si];
  if (!dir) return '';
  const month = (it.date || '0000').slice(0, 7);
  const key = dir + '/' + month;
  if (bodyCache[key] === undefined) {
    const months = bodyMeta[dir];
    if (months && months.indexOf(month) === -1) {   // 该月没有正文分片，直接跳过
      bodyCache[key] = {};
      return '';
    }
    try {
      const r = await fetch('data/body/' + key + '.json');
      bodyCache[key] = r.ok ? await r.json() : {};
    } catch (e) { bodyCache[key] = {}; }
  }
  return bodyCache[key][it.id] || '';
}

const readerMask = document.getElementById('readerMask');
const readerMeta = document.getElementById('readerMeta');
const readerTitle = document.getElementById('readerTitle');
const readerBody = document.getElementById('readerBody');
const readerSrc = document.getElementById('readerSrc');

// 站内阅读：直接在当前页打开正文，正文按需拉取分片
async function openReader(id) {
  const it = DATA.find(x => x.id === id);
  if (!it) return;
  readerMeta.innerHTML = tagFor(it.si) + '<span>' + esc(it.date || '日期未知') + '</span>' +
    (isRecent(it.date) ? '<span class="badge-new">新</span>' : '');
  readerTitle.textContent = it.title || '(无标题)';
  readerBody.innerHTML = '<div class="empty">正文加载中…</div>';
  readerBody.scrollTop = 0;
  readerSrc.href = it.url || '#';
  readerMask.classList.add('open');
  document.body.style.overflow = 'hidden';
  history.replaceState(null, '', '#item=' + id);

  const c = (await getBody(it)).trim();
  const isForum = !!SUMMARY_ONLY[SRC_NAMES[it.si]];
  if (!c) {
    const note = isForum
      ? '该帖正文需登录论坛才可见，暂未收录。可点击右上角「官网原文」查看完整内容。'
      : '本条正文未抓取到，请点击右上角「官网原文」查看。';
    readerBody.innerHTML = '<div class="reader-note">' + note + '</div>';
  } else if (isForum) {
    readerBody.innerHTML =
      '<div class="reader-note">论坛帖完整正文需登录才可见，以下为 RSS 摘要（' + c.length +
      ' 字）。完整内容请点右上角「官网原文」。</div>' +
      '<div class="reader-text">' + esc(c) + '</div>';
  } else {
    readerBody.innerHTML = '<div class="reader-text">' + esc(c) + '</div>';
  }
  readerBody.scrollTop = 0;
}

function closeReader() {
  readerMask.classList.remove('open');
  document.body.style.overflow = '';
  history.replaceState(null, '', location.pathname + location.search);
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeReader(); });
// 支持用 #item=<id> 直接分享/刷新后仍打开同一篇（脚本位于页面末尾，DOM 已就绪）
async function openFromHash() {
  const m = location.hash.match(/^#item=(.+)$/);
  if (!m || !DATA.length) return;              // 首屏索引未就绪时忽略
  if (!DATA.some(x => x.id === m[1])) await ensureAll();   // 可能是未加载的旧条目
  openReader(m[1]);
}
window.addEventListener('hashchange', openFromHash);

// 判断日期是否为今天（北京时间，用于「新」高亮：仅今天更新的标新）
function isRecent(d) {
  if (!d) return false;
  const bj = new Date(Date.now() + 8 * 3600000); // 北京时间 UTC+8
  const pad = n => String(n).padStart(2, '0');
  const today = bj.getUTCFullYear() + '-' + pad(bj.getUTCMonth() + 1) + '-' + pad(bj.getUTCDate());
  return d === today;
}

// 日期相对标签（今天 / 昨天 / 具体日期）
function dayLabel(d) {
  const pad = n => String(n).padStart(2, '0');
  const t = new Date();
  const ts = t.getFullYear() + '-' + pad(t.getMonth() + 1) + '-' + pad(t.getDate());
  const y = new Date(Date.now() - 86400000);
  const ys = y.getFullYear() + '-' + pad(y.getMonth() + 1) + '-' + pad(y.getDate());
  if (d === ts) return '<span class="today-flag">今天</span> · ' + d;
  if (d === ys) return '昨天 · ' + d;
  return d;
}

// 折叠/展开某一天
function toggleDay(head) {
  head.parentElement.classList.toggle('open');
}

// 生成某一天的看板块
function buildDay(d, items, open) {
  const summary = DAILY[d] || '';
  const bySrc = {};
  items.forEach(it => { const k = SRC_NAMES[it.si]; (bySrc[k] = bySrc[k] || []).push(it); });
  const srcBlocks = Object.keys(bySrc).map(src => {
    const cards = bySrc[src].map(it =>
      '<div class="d-card">' + tagFor(it.si) +
      '<a onclick="openReader(\\'' + it.id + '\\')">' + esc(it.title) + '</a></div>'
    ).join('');
    return '<div class="d-src"><div class="d-src-name">' + esc(src) + ' · ' + bySrc[src].length + ' 条</div>' + cards + '</div>';
  }).join('');
  const title = d === '更早' ? '更早 · ' + items.length + ' 条' : dayLabel(d);
  return '<div class="day-group' + (open ? ' open' : '') + '">' +
    '<div class="day-head" onclick="toggleDay(this)">' +
      '<div class="day-title">' + title + '</div>' +
      '<div class="day-summary">' + esc(summary) + '</div>' +
      '<span class="day-arrow">▾</span>' +
    '</div>' +
    '<div class="day-body">' + srcBlocks + '</div>' +
  '</div>';
}

// 渲染每日更新看板：最近 14 天每天一组，更早的合并
function renderDaily() {
  const groups = {};
  DATA.forEach(it => {
    const d = it.date || '未知';
    (groups[d] = groups[d] || []).push(it);
  });
  const days = Object.keys(groups).sort().reverse();
  const recentDays = days.slice(0, 14);
  const oldDays = days.slice(14);
  let blocks = recentDays.map((d, i) => buildDay(d, groups[d], i < 2)).join('');
  if (oldDays.length) {
    const oa = [];
    for (const d of oldDays) for (const it of groups[d]) oa.push(it);
    blocks += buildDay('更早', oa.slice(0, 400), false);   // 上限 400 条，避免一次插入过多 DOM
  }
  dailyBoard.innerHTML = blocks;
}

function cardHtml(it) {
  const isNew = isRecent(it.date);
  return '<div class="card' + (isNew ? ' new' : '') + '">' +
    '<div class="meta">' + tagFor(it.si) + '<span>' + esc(it.date || '日期未知') + '</span>' +
      (isNew ? '<span class="badge-new">新</span>' : '') +
      '<a class="src-link" href="' + esc(it.url) + '" target="_blank" rel="noopener">官网原文 ↗</a></div>' +
    '<h2><a onclick="openReader(\\'' + it.id + '\\')">' + esc(it.title) + '</a></h2>' +
    '</div>';
}

function render() {
  const q = kw.toLowerCase();
  filtered = DATA.filter(it => {
    if (src !== 'all' && !(MATCH[src] || []).includes(SRC_NAMES[it.si])) return false;
    if (q && !(it.title || '').toLowerCase().includes(q)) return false;
    return true;
  });
  const partial = !allLoaded;
  count.textContent = '共 ' + filtered.length.toLocaleString() + ' 条' + (partial ? '（已加载部分）' : '');
  shown = 0;
  list.innerHTML = '';
  if (!filtered.length) {
    list.innerHTML = '<div class="empty">没有匹配的结果</div>';
  } else {
    appendMore();
  }
  if (partial) {
    list.insertAdjacentHTML('beforeend',
      '<div class="load-all-wrap"><button id="loadAll" class="load-all-btn"></button></div>');
    updateLoadAllBtn();
  }
}

// 点击「加载全部」：拉完所有来源分片后重新渲染
list.addEventListener('click', async e => {
  if (e.target.id !== 'loadAll') return;
  e.target.disabled = true;
  e.target.textContent = '正在加载全部索引…';
  await ensureAll();
  renderDaily();
  render();
});

// 分批渲染，避免一次插入过多 DOM 造成卡顿
function appendMore() {
  const next = filtered.slice(shown, shown + PAGE);
  if (!next.length) return;
  const s = document.getElementById('moreSentinel');
  if (s) s.remove();
  list.insertAdjacentHTML('beforeend', next.map(cardHtml).join(''));
  shown += next.length;
  if (shown < filtered.length) {
    list.insertAdjacentHTML('beforeend', '<div id="moreSentinel" class="empty" style="padding:16px 0">向下滚动加载更多…</div>');
  }
}

// 滚动到底部自动加载下一批
window.addEventListener('scroll', () => {
  if (shown < filtered.length && window.innerHeight + window.scrollY >= document.body.offsetHeight - 400) {
    appendMore();
  }
});

document.getElementById('q').addEventListener('input', async e => {
  kw = e.target.value.trim();
  if (kw && !allLoaded) {                       // 搜索需要全量索引，首次搜索时补齐
    count.textContent = '正在加载全部索引以搜索…';
    await ensureAll();
    renderDaily();
  }
  render();
});
document.getElementById('sidebar').addEventListener('click', async e => {
  const item = e.target.closest('.nav-item');
  if (!item) return;
  // 父级点击：切换子分类展开/收起
  if (item.classList.contains('nav-parent')) {
    item.classList.toggle('open');
    const children = item.nextElementSibling;
    if (children && children.classList.contains('nav-children')) {
      children.classList.toggle('open', item.classList.contains('open'));
    }
  }
  document.querySelectorAll('.nav-item').forEach(c => c.classList.remove('active'));
  item.classList.add('active');
  src = item.dataset.src;
  // 该分类涉及的来源若尚未加载，先加载（避免只看到首屏那部分）
  const need = (MATCH[src] || []).filter(n => !loadedDirs.has(SRC_DIR[SRC_NAMES.indexOf(n)]));
  if (need.length) {
    count.textContent = '加载中…';
    list.innerHTML = '<div class="empty">正在加载「' + need.join('、') + '」…</div>';
    for (const n of (MATCH[src] || [])) await ensureSource(SRC_NAMES.indexOf(n));
    renderDaily();
  }
  render();
});

// Tab 切换：分类浏览 / 每日更新
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    const isDaily = tab.dataset.tab === 'daily';
    document.getElementById('view-browse').style.display = isDaily ? 'none' : '';
    document.getElementById('view-daily').style.display = isDaily ? '' : 'none';
    if (isDaily) renderDaily();
  });
});

init();
</script>
</body>
</html>"""

    html = (html.replace("__NAV__", nav_html).replace("__SITES__", sites_html)
                .replace("__MATCH__", match_js)
                .replace("__DAILY__", daily_js)
                .replace("__TOTAL__", str(total))
                .replace("__LATEST__", latest_date).replace("__CHECK__", check_time))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已生成 {OUT}，共 {total} 条数据")


if __name__ == "__main__":
    main()
