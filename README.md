# 会计信息聚合工作台

聚合「国家税务局、中注协、中国会计视野」的公告与处罚案例，供个人学习查阅。抓取脚本 + 静态页面，通过 GitHub Actions 定时自动更新，GitHub Pages 免费发布。

## 项目结构

```
├── fetcher/             # 抓取模块
│   ├── common.py        # 请求 + URL md5 唯一键
│   ├── cicpa.py         # 中注协执业质量检查通告
│   └── esnai.py         # 中国会计视野看点
├── main.py              # 入口：抓列表 → 去重 → 抓正文 → 落盘 data/items.json
├── preview.py           # 读 items.json 生成 index.html（自包含，内嵌数据）
├── requirements.txt
└── .github/workflows/update.yml   # 每天定时抓取 + 自动发布
```

## 本地运行

```bash
pip install -r requirements.txt
python main.py       # 抓取数据
python preview.py    # 生成 index.html
```

## 部署到 GitHub Pages（自动更新）

1. 新建 GitHub 仓库（建议 public），把本项目推上去。
2. 仓库 Settings → Pages → Source 选 `Deploy from a branch` → 分支 `main` / 目录 `/ (root)` → Save。
3. 到 Actions 页手动触发一次 `daily-update` 工作流（或等它每天定时跑）。
4. 工作流会自动抓取、生成 `index.html` 并推送回 `main`，Pages 随即自动发布。
5. 访问 `https://<用户名>.github.io/<仓库名>/` 即可。

## 数据源

| 来源 | 栏目 | 说明 |
|------|------|------|
| 中注协 cicpa.org.cn | 执业质量检查通告 | 事务所违规 + 行业惩戒 |
| 会计视野 esnai.cn | 看点/行业 | 处罚案例、行业动态 |

注：国家税务局政策法规库（fgk.chinatax.gov.cn）待接入。
