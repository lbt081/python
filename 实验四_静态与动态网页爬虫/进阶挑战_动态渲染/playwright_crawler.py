# -*- coding: utf-8 -*-
"""进阶挑战：基于 Playwright 的动态渲染列表页爬虫。

内置两个动态站点配置（--site 选择）：
    quotes_scroll  https://quotes.toscrape.com/scroll
        - 初始 HTML 中没有名言数据，数据由 JavaScript 动态渲染；
        - 无限滚动，边滚动边加载，最终 100 条。
    quotes_js      https://quotes.toscrape.com/js/
        - 同样是 JavaScript 渲染，但采用普通分页，10 页共 100 条。

运行方式（在“进阶挑战_动态渲染”目录执行）：
    python -m pip install -r requirements-dynamic.txt
    python -m playwright install chromium
    python playwright_crawler.py --site quotes_scroll --headed
    python playwright_crawler.py --site quotes_js --headed

输出（不写 --output 时）：
    result_quotes_dynamic.csv        无限滚动结果，100 条名言，3 列，utf-8-sig
    result_quotes_js_dynamic.csv     JS 分页结果，100 条名言，3 列，utf-8-sig
    quotes_dynamic_page.png          渲染后的页面截图（便于答辩展示）
    quotes_js_dynamic_page.png
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin

import pandas as pd
from playwright.sync_api import (
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


DEFAULT_FIELDS: List[Dict[str, str]] = [
    {"label": "名言", "selector": "span.text", "kind": "text"},
    {"label": "作者", "selector": "small.author", "kind": "text"},
    {"label": "标签", "selector": "div.tags a.tag", "kind": "text_all"},
]


# 动态站点配置：同一套浏览器渲染流程，适配不同页面结构和翻页方式
SITE_CONFIGS: Dict[str, Dict] = {
    "s": {
        "name": "Quotes 无限滚动",
        "url": "https://quotes.toscrape.com/scroll",
        "item_selector": "div.quote",
        "fields": DEFAULT_FIELDS,
        "next_selector": "",
        "scroll_rounds": 40,
        "max_pages": 1,
        "output": "result_quotes_dynamic.csv",
        "screenshot": "quotes_dynamic_page.png",
    },
    "quotes_js": {
        "name": "Quotes JavaScript 分页",
        "url": "https://quotes.toscrape.com/js/",
        "item_selector": "div.quote",
        "fields": DEFAULT_FIELDS,
        "next_selector": "li.next a",
        "scroll_rounds": 0,
        "max_pages": 10,
        "output": "result_quotes_js_dynamic.csv",
        "screenshot": "quotes_js_dynamic_page.png",
    },
}


class PlaywrightDynamicCrawler:
    """用真实浏览器渲染动态页面，再从 DOM 中提取列表数据。"""

    def __init__(
        self,
        target_url: str,
        output_file: str = "result_quotes_dynamic.csv",
        max_pages: int = 1,
        headless: bool = True,
        page_interval: float = 2.0,
        timeout_ms: int = 20000,
        item_selector: str = "div.quote",
        next_selector: str = "",
        fields: Optional[List[Dict[str, str]]] = None,
        scroll_rounds: int = 40,
        scroll_wait_ms: int = 600,
        page_screenshot: str = "",
    ) -> None:
        self.target_url = target_url
        self.output_file = Path(output_file)
        self.max_pages = max_pages
        self.headless = headless
        self.page_interval = page_interval
        self.timeout_ms = timeout_ms
        self.item_selector = item_selector
        self.next_selector = next_selector
        self.fields = fields or DEFAULT_FIELDS
        self.scroll_rounds = scroll_rounds
        self.scroll_wait_ms = scroll_wait_ms
        self.page_screenshot = page_screenshot

    @staticmethod
    def _extract_field(item: Locator, field: Dict[str, str], page_url: str) -> str:
        """在单条记录内部按配置提取一个字段，缺失时返回空字符串。"""
        selector = field.get("selector", "")
        kind = field.get("kind", "text")
        if not selector:
            return ""

        locator = item.locator(selector)
        if locator.count() == 0:
            return ""

        first = locator.first
        if kind == "text":
            return first.inner_text().strip()

        if kind == "title":
            return (first.get_attribute("title") or first.inner_text()).strip()

        if kind == "href":
            href = (first.get_attribute("href") or "").strip()
            return urljoin(page_url, href) if href else ""

        if kind == "text_all":
            values = []
            for index in range(locator.count()):
                value = locator.nth(index).inner_text().strip()
                if value:
                    values.append(value)
            return " / ".join(values)

        return first.inner_text().strip()

    def _parse_current_page(self, page: Page, page_url: str) -> List[Dict[str, str]]:
        """解析当前已渲染页面中的全部记录。"""
        records: List[Dict[str, str]] = []
        items = page.locator(self.item_selector)

        for index in range(items.count()):
            item = items.nth(index)
            try:
                record = {
                    field["label"]: self._extract_field(item, field, page_url)
                    for field in self.fields
                }
                records.append(record)
            except Exception as exc:
                print(f"[警告] 第{index + 1}条解析失败，已跳过：{exc}")

        return records

    def _auto_scroll(self, page: Page) -> None:
        """小步向下滚动，触发无限加载；连续多轮条数不变时停止。"""
        previous_count = 0
        stable_rounds = 0

        for round_no in range(1, self.scroll_rounds + 1):
            page.evaluate("window.scrollBy(0, 700)")
            page.wait_for_timeout(self.scroll_wait_ms)
            count = page.locator(self.item_selector).count()
            print(f"滚动第{round_no}轮：当前解析到 {count} 条")

            if count == previous_count:
                stable_rounds += 1
            else:
                stable_rounds = 0
            previous_count = count

            if stable_rounds >= 5:
                print("连续 5 轮条数没有变化，停止滚动")
                break

    def _find_next_page_url(self, page: Page, page_url: str) -> Optional[str]:
        """查找下一页链接；无限滚动站点不配置 next_selector，返回 None。"""
        if not self.next_selector:
            return None

        candidates = page.locator(self.next_selector)
        if candidates.count() > 0:
            href = (candidates.first.get_attribute("href") or "").strip()
            if href:
                return urljoin(page_url, href)

        for text in ("下一页", "下一頁", ">", "»"):
            locator = page.locator(
                f'.pager a:text-is("{text}"), .pagination a:text-is("{text}")'
            )
            if locator.count() > 0:
                href = (locator.first.get_attribute("href") or "").strip()
                if href:
                    return urljoin(page_url, href)

        return None

    def save_data(self, records: List[Dict[str, str]]) -> None:
        """按字段顺序保存 CSV；同一行完全重复时只保留第一条。"""
        columns = [field["label"] for field in self.fields]
        unique_records = []
        seen = set()
        for record in records:
            key = tuple(record.get(column, "") for column in columns)
            if key in seen:
                continue
            seen.add(key)
            unique_records.append(record)

        removed = len(records) - len(unique_records)
        if removed:
            print(f"[提示] 去除重复行 {removed} 条")

        df = pd.DataFrame(unique_records, columns=columns)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(self.output_file, index=False, encoding="utf-8-sig")
        print(f"CSV 已保存：{self.output_file}（{len(df)} 行数据 + 1 行表头）")
        return len(df)

    def run(self) -> List[Dict[str, str]]:
        """主流程：启动浏览器 → 渲染页面 → 滚动加载 → 解析 → 保存。"""
        all_records: List[Dict[str, str]] = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="zh-CN",
                viewport={"width": 1366, "height": 900},
            )

            try:
                page = context.new_page()
                current_url: Optional[str] = self.target_url
                visited = set()
                page_no = 0

                while (
                    current_url
                    and current_url not in visited
                    and page_no < self.max_pages
                ):
                    visited.add(current_url)
                    page_no += 1

                    if page_no > 1:
                        time.sleep(self.page_interval)

                    print(f"\n正在加载第{page_no}页：{current_url}")
                    try:
                        page.goto(
                            current_url,
                            wait_until="domcontentloaded",
                            timeout=self.timeout_ms,
                        )
                        # 关键：等待 JavaScript 把列表项渲染到 DOM 中
                        page.wait_for_selector(
                            self.item_selector,
                            timeout=self.timeout_ms,
                        )
                        self._auto_scroll(page)
                    except PlaywrightTimeoutError:
                        print(f"[错误] 第{page_no}页等待目标元素超时，停止抓取")
                        break

                    records = self._parse_current_page(page, current_url)
                    all_records.extend(records)
                    print(f"第{page_no}页解析到 {len(records)} 条数据")

                    if self.page_screenshot and page_no == 1:
                        try:
                            # 截图前回到顶部，画面从标题和第一条数据开始，便于答辩展示
                            page.evaluate("window.scrollTo(0, 0)")
                            page.wait_for_timeout(300)
                            page.screenshot(path=self.page_screenshot, full_page=False)
                            print(f"页面截图已保存：{self.page_screenshot}")
                        except Exception as exc:
                            print(f"[提示] 页面截图保存失败：{exc}")

                    current_url = self._find_next_page_url(page, current_url)

            except Exception as exc:
                print(f"[错误] 爬虫运行发生未预期异常：{exc}")
            finally:
                context.close()
                browser.close()

        saved_count = self.save_data(all_records)
        print(f"\n抓取完成，原始 {len(all_records)} 条，去重后 {saved_count} 条")
        return all_records


def main() -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(
        description="Playwright 动态渲染列表页爬虫（进阶挑战）"
    )
    parser.add_argument(
        "--site",
        default="quotes_scroll",
        choices=sorted(SITE_CONFIGS),
        help="动态站点配置，默认 quotes_scroll",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="自定义目标 URL；不填则使用 --site 配置中的地址",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="CSV 输出路径；不填则使用站点配置的默认文件名",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=None,
        help="最多抓几页；不填则使用站点配置的默认页数",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="显示浏览器窗口，便于现场演示；默认无头模式",
    )
    parser.add_argument(
        "--screenshot",
        default=None,
        help="首屏截图路径；不填则使用站点配置，传空字符串可关闭",
    )
    args = parser.parse_args()

    site = SITE_CONFIGS[args.site]
    target_url = args.url or site["url"]
    output_file = args.output or site["output"]
    screenshot = site["screenshot"] if args.screenshot is None else args.screenshot
    max_pages = args.pages if args.pages and args.pages > 0 else site.get("max_pages", 1)

    next_selector = site.get("next_selector", "")
    if args.url and args.url.rstrip("/").endswith("/js"):
        next_selector = "li.next a"

    print("=" * 60)
    print("进阶挑战：Playwright 动态渲染爬虫")
    print("=" * 60)
    print(f"站点配置：{args.site}（{site['name']}）")
    print(f"目标页面：{target_url}")
    print(f"输出文件：{output_file}")
    print(f"运行模式：{'有头（可见浏览器）' if args.headed else '无头（headless）'}")

    crawler = PlaywrightDynamicCrawler(
        target_url=target_url,
        output_file=output_file,
        max_pages=max_pages,
        headless=not args.headed,
        item_selector=site["item_selector"],
        next_selector=next_selector,
        fields=site["fields"],
        scroll_rounds=site["scroll_rounds"],
        page_screenshot=screenshot,
    )
    crawler.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
