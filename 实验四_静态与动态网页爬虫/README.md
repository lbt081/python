# 实验四：静态与动态网页爬虫

> 刘宝廷 ｜ 3242052051028 ｜ 软工24-2班

基础任务：基于 requests + BeautifulSoup4 的通用静态列表页爬虫，站点差异全部写在 `sites.json` 中，**一次运行一个站点**；抓取结果用 pandas 导出 `utf-8-sig` 编码的 CSV。新增站点只需改配置，不改 Python 代码。

进阶挑战：用 Playwright 启动真实 Chromium，抓取 JavaScript 动态渲染的无限滚动页面（Quotes `/scroll`），代码独立放在 `进阶挑战_动态渲染/`。

## 目录结构

```
universal_crawler.py        # 通用静态爬虫主程序
sites.json                  # 4 个站点配置：入口 URL、列表项、字段、下一页
result.csv                  # 博客园结果，320 条
universal_output/
├── books.csv               # 40 条
├── quotes.csv              # 10 条
└── countries.csv           # 250 条

进阶挑战_动态渲染/
├── playwright_crawler.py   # Playwright 动态渲染主程序（支持 --site 选择动态页面）
├── verify.py               # env / static / csv 三种验证
├── result_quotes_dynamic.csv      # 100 条名言，无限滚动
├── result_quotes_js_dynamic.csv   # 100 条名言，JavaScript 分页
├── quotes_dynamic_page.png
├── quotes_js_dynamic_page.png
├── 运行截图/                # 动态抓取证据
└── 进阶挑战说明-Playwright动态渲染.docx

运行截图/                     # 6 张静态多站点运行截图
实验报告-静态与动态网页爬虫.docx      # 含 6.7 动态渲染进阶结果
AI协作过程记录-静态与动态网页爬虫.docx
运行说明.docx
系统流程图.png
requirements.txt
```

## 运行环境

```bash
pip install -r requirements.txt
```

## 使用方式

```bash
# 查看已配置站点
python universal_crawler.py --list

# 主站：博客园全部 16 页，输出 result.csv
python universal_crawler.py --site cnblogs --output result.csv

# 其他站点
python universal_crawler.py --site books --pages 2
python universal_crawler.py --site quotes --pages 1
python universal_crawler.py --site countries --pages 1
```

未指定 `--output` 时，结果默认保存到 `universal_output/<站点名>.csv`；`--pages 0` 表示不限制页数。

## 结果摘要

| 站点 | 页数 | 条数 | 输出 |
| --- | --- | --- | --- |
| 博客园 Python 分类 | 16 | 320 | result.csv（321 行含表头） |
| Books to Scrape | 2 | 40 | universal_output/books.csv |
| Quotes to Scrape | 1 | 10 | universal_output/quotes.csv |
| Countries of the World | 1 | 250 | universal_output/countries.csv |

## 进阶挑战：Playwright 动态渲染

动态部分提供两个配置，覆盖两种常见的动态加载方式：

| 站点配置 | 目标页面 | 加载方式 | 结果 |
| --- | --- | --- | --- |
| `quotes_scroll` | `quotes.toscrape.com/scroll` | JavaScript 渲染 + 无限滚动 | 100 条 |
| `quotes_js` | `quotes.toscrape.com/js/` | JavaScript 渲染 + 分页 | 100 条 |

`requests` 对这两个页面的初始 HTML 都只能解析 0 条；Playwright 启动 Chromium、等待 DOM 渲染后才拿到数据。

```bash
cd 进阶挑战_动态渲染
python -m pip install -r requirements-dynamic.txt
python -m playwright install chromium

python verify.py env       # Playwright 版本 + Chromium 启动
python verify.py static    # requests 初始 HTML：0 条

python playwright_crawler.py --site quotes_scroll
python playwright_crawler.py --site quotes_js

python verify.py csv       # 默认校验 result_quotes_dynamic.csv
python verify.py csv --csv result_quotes_js_dynamic.csv
```

- 不写 `--output` 时，两个站点分别保存为 `result_quotes_dynamic.csv` 和 `result_quotes_js_dynamic.csv`
- 指定输出与静态一致：`--output my_result.csv`
- `quotes_js` 默认抓 10 页，共 100 条；`quotes_scroll` 滚到条数稳定为止

## 新增站点

在 `sites.json` 中复制一段配置，修改 `start_url`、`item_selector`、`fields` 和 `next_selector` 即可：

```json
"mysite": {
  "name": "新站点",
  "start_url": "https://example.com/list",
  "item_selector": "article.item",
  "fields": [
    {"label": "标题", "selector": "h2 a", "kind": "text"},
    {"label": "详情链接", "selector": "h2 a", "kind": "href"}
  ],
  "next_selector": "li.next a"
}
```

```bash
python universal_crawler.py --site mysite --pages 1
```

## 说明

- 演示站点均为公开练习站点；抓取前请确认 robots.txt 与数据使用授权，默认 2 秒间隔不要改小。
- 基础任务只使用静态方案；动态渲染在独立的 `进阶挑战_动态渲染/` 中完成，不改变基础任务的工具约束。
- `.docx` 文件在 GitHub 上无法在线预览，点击文件后选择 Download 查看。
