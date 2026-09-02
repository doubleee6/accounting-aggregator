# -*- coding: utf-8 -*-
"""把 data/items.json 渲染成静态预览页（顶部官网直达 + 左导航 + 右内容）。"""
import json
import os
from collections import Counter

DATA = os.path.join("data", "items.json")
OUT = "index.html"

# 顶部官网直达入口
OFFICIAL_SITES = [
    {"name": "国家税务总局", "url": "https://www.chinatax.gov.cn/"},
    {"name": "中国注册会计师协会", "url": "https://www.cicpa.org.cn/"},
    {"name": "中国会计视野", "url": "https://www.esnai.cn/"},
    {"name": "中国注册税务师协会", "url": "https://www.cctaa.cn/"},
    {"name": "财政部", "url": "https://www.mof.gov.cn/"},
    {"name": "函证导航", "url": "https://confirm.maoyanqing.com/"},
]


def main():
    with open(DATA, "r", encoding="utf-8") as f:
        items = json.load(f)

    items = [it for it in items if it.get("title")]
    items.sort(key=lambda x: x.get("date", ""), reverse=True)
    counts = Counter(it.get("source", "") for it in items)
    total = len(items)

    data_js = json.dumps(items, ensure_ascii=False)

    # 左侧分类导航（支持两级：中国会计视野 → CPA业务探讨/内部审计）
    GROUPS = [
        ("国家税务局", None),
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
<style>
  :root {
    --bg: #f4f5f7; --card: #ffffff; --text: #1a1d21; --muted: #8a919f;
    --primary: #0f766e; --primary-soft: #e6f4f1; --border: #e7e9ee;
    --tax: #b45309; --tax-bg: #fef3c7;
    --cicpa: #0f766e; --cicpa-bg: #ccfbf1;
    --esnai: #1d4ed8; --esnai-bg: #dbeafe;
    --cpa: #7c3aed; --cpa-bg: #ede9fe;
    --audit: #be185d; --audit-bg: #fce7f3;
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

  @media (max-width: 720px) {
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
    <div>
      <h1>会计信息聚合工作台</h1>
      <p>聚合税务 · 注协 · 会计视野的公告与处罚案例</p>
    </div>
  </header>

  <div class="quick-links">
__SITES__
  </div>

  <div class="searchbar">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    <input type="search" id="q" placeholder="搜索标题或正文关键词，如：增值税 / 公开谴责 / 函证">
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
<script>
const DATA = __DATA__;
const MATCH = __MATCH__;
const list = document.getElementById('list');
const count = document.getElementById('count');
let src = 'all';
let kw = '';

function esc(s) { return (s || '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

function tagFor(source) {
  if (source === '中注协') return '<span class="tag cicpa">中注协</span>';
  if (source === '国家税务局') return '<span class="tag tax">国家税务局</span>';
  if (source === 'CPA业务探讨') return '<span class="tag cpa">CPA业务探讨</span>';
  if (source === '内部审计') return '<span class="tag audit">内部审计</span>';
  return '<span class="tag esnai">会计视野</span>';
}

// 判断日期是否在最近 30 天内（用于「新」高亮）
function isRecent(d) {
  if (!d) return false;
  const t = new Date(d + 'T00:00:00');
  if (isNaN(t)) return false;
  const diff = (Date.now() - t.getTime()) / 86400000;
  return diff >= 0 && diff <= 30;
}

function render() {
  const q = kw.toLowerCase();
  const rows = DATA.filter(it => {
    if (src !== 'all' && !(MATCH[src] || []).includes(it.source)) return false;
    if (q && !(it.title + ' ' + (it.content || '')).toLowerCase().includes(q)) return false;
    return true;
  });
  count.textContent = '共 ' + rows.length + ' 条';
  if (!rows.length) {
    const tip = '没有匹配的结果';
    list.innerHTML = '<div class="empty">' + tip + '</div>';
    return;
  }
  list.innerHTML = rows.map(it => {
    const sum = (it.content || '').slice(0, 140).replace(/\\n/g, ' ');
    const isNew = isRecent(it.date);
    const newClass = isNew ? ' new' : '';
    const newBadge = isNew ? '<span class="badge-new">新</span>' : '';
    return '<div class="card' + newClass + '">' +
      '<div class="meta">' + tagFor(it.source) + '<span>' + esc(it.date || '日期未知') + '</span>' + newBadge + '</div>' +
      '<h2><a href="' + esc(it.url) + '" target="_blank" rel="noopener">' + esc(it.title) + '</a></h2>' +
      (sum ? '<div class="sum">' + esc(sum) + '…</div>' : '<div class="sum">（正文待抓取）</div>') +
      '</div>';
  }).join('');
}

document.getElementById('q').addEventListener('input', e => { kw = e.target.value.trim(); render(); });
document.getElementById('sidebar').addEventListener('click', e => {
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
  render();
});
render();
</script>
</body>
</html>"""

    html = html.replace("__NAV__", nav_html).replace("__SITES__", sites_html).replace("__DATA__", data_js).replace("__MATCH__", match_js)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已生成 {OUT}，共 {total} 条数据")


if __name__ == "__main__":
    main()
