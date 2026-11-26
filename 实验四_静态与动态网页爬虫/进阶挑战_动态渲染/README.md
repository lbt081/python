# 进阶挑战：Playwright 动态渲染爬虫

> 实验四进阶挑战 ｜ 刘宝廷 ｜ 3242052051028 ｜ 软工24-2班

## 目标

静态方案只能抓取初始 HTML 中已有的数据。本进阶挑战使用 Playwright 启动真实 Chromium 浏览器，
执行 JavaScript 并等待 DOM 渲染，再抓取 **无限滚动** 页面：

- 目标：<https://quotes.toscrape.com/scroll>
- 初始 HTML：2671 字节，`div.quote` 和 `span.text` 均为 0 个
- 渲染并滚动后：100 条名言
- 输出：`result_quotes_dynamic.csv`（100 行 × 3 列，utf-8-sig）

## 文件说明

```
playwright_crawler.py                 动态渲染主程序
verify.py                             环境 / 静态对比 / CSV 校验脚本
requirements-dynamic.txt              依赖清单
result_quotes_dynamic.csv             抓取结果，100 条
quotes_dynamic_page.png               渲染后的页面截图
run_log.txt                           实际运行日志
运行截图/                              5 张运行过程截图
进阶挑战说明-Playwright动态渲染.docx    设计、代码讲解与结果说明
```

## 安装与运行

```bash
python -m pip install -r requirements-dynamic.txt
python -m playwright install chromium

# 环境检查：版本 + 实际启动一次 Chromium
python verify.py env

# 证明 requests 拿不到数据
python verify.py static

# 动态抓取（默认无头；加 --headed 可看到浏览器）
python playwright_crawler.py

# 校验 CSV：shape、列名、前 3 条
python verify.py csv
```

## 核心流程

1. `sync_playwright()` 启动 Playwright。
2. `chromium.launch(headless=True)` 启动浏览器，`new_context()` 设置 UA、语言和视口。
3. `page.goto(..., wait_until="domcontentloaded")` 打开页面。
4. `page.wait_for_selector("div.quote")` 等待 JavaScript 把列表渲染到 DOM。
5. `_auto_scroll()` 反复滚动到底部，触发无限加载，直到页面高度稳定。
6. 用 `page.locator()` 在每条记录内部提取名言、作者、标签。
7. `pandas` 保存 CSV，`utf-8-sig` 保证 Excel 中文不乱码。
8. `finally` 中关闭 context 和 browser，避免进程残留。

## 与静态方案的区别

| 维度 | requests + BeautifulSoup4 | Playwright |
| --- | --- | --- |
| 数据来源 | 初始 HTML | JS 执行后的 DOM |
| 本页结果 | 0 条 | 100 条 |
| 依赖 | requests、bs4 | playwright + Chromium |
| 速度/资源 | 快、低 | 慢、高 |
| 适用 | 静态列表页 | 动态渲染、无限滚动、复杂交互 |

## 边界

- 本进阶只用于公开练习站点，不绕过登录、付费墙或验证码。
- 动态页面结构变化同样会导致选择器失效，需要更新 `fields`。
- 无限滚动必须设置轮次上限，并按条目或详情链接去重。
- 浏览器自动化资源消耗高，能用 XHR 接口时优先用接口。

> `.docx` 说明文档需下载后查看；`运行截图/` 内含环境检查、静态对比、动态抓取、CSV 校验和渲染页面 5 张图。
