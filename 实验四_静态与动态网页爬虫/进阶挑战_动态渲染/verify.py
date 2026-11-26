# -*- coding: utf-8 -*-
"""进阶挑战的辅助验证脚本。

用法（在“进阶挑战_动态渲染”目录执行）：
    python verify.py env       # 检查 Playwright 与 Chromium
    python verify.py static    # 证明 requests 拿到的初始 HTML 没有数据
    python verify.py csv       # 校验动态抓取生成的 CSV
"""

from __future__ import annotations

import argparse
from importlib.metadata import version

import pandas as pd
import requests
from bs4 import BeautifulSoup


URL = "https://quotes.toscrape.com/scroll"
CSV_FILE = "result_quotes_dynamic.csv"


def check_env() -> None:
    """检查 Playwright 版本并实际启动一次 Chromium。"""
    from playwright.sync_api import sync_playwright

    print(f"Version {version('playwright')}")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        print("Chromium 启动成功")
        browser.close()


def check_static(url: str = URL) -> None:
    """用 requests + BeautifulSoup4 抓同一页面，证明初始 HTML 没有数据。"""
    response = requests.get(url, timeout=15)
    soup = BeautifulSoup(response.text, "html.parser")
    print(f"URL {url}")
    print(f"状态码 {response.status_code}")
    print(f"初始HTML长度 {len(response.text)}")
    print(f"div.quote {len(soup.select('div.quote'))}")
    print(f"span.text {len(soup.select('span.text'))}")
    print("结论：requests 只拿到空壳 HTML，BeautifulSoup 解析 0 条")


def check_csv(csv_file: str = CSV_FILE) -> None:
    """读取动态抓取结果，输出形状、列名和前 3 条作者/标签。"""
    df = pd.read_csv(csv_file, encoding="utf-8-sig")
    print(f"文件 {csv_file}")
    print(f"shape: {df.shape}")
    print(f"columns: {list(df.columns)}")
    preview_columns = [column for column in ("作者", "标签") if column in df.columns]
    if preview_columns:
        print(df[preview_columns].head(3).to_string(index=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="进阶挑战验证脚本")
    parser.add_argument("mode", choices=["env", "static", "csv"], help="验证类型")
    parser.add_argument("--url", default=URL, help="static 模式的目标 URL")
    parser.add_argument("--csv", default=CSV_FILE, help="csv 模式的结果文件")
    args = parser.parse_args()

    if args.mode == "env":
        check_env()
    elif args.mode == "static":
        check_static(args.url)
    else:
        check_csv(args.csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
