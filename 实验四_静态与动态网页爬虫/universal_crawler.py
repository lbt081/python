import argparse
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup


class UniversalCrawler:
    """配置驱动的通用静态列表页爬虫。

    核心流程（请求、重试、限速、翻页、CSV）对所有站点共用；
    站点差异全部来自 sites.json 中的 item_selector、fields、next_selector。
    """

    TIMEOUT = 10
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    def __init__(
        self,
        site_name: str,
        config: Dict,
        output_dir: str = "universal_output",
        output_file: Optional[str] = None,
        max_pages: Optional[int] = 1,
        max_retries: int = 3,
        page_interval: float = 2,
    ) -> None:
        self.site_name = site_name
        self.config = config
        self.output_dir = Path(output_dir)
        self.max_pages = max_pages
        self.max_retries = max_retries
        self.page_interval = page_interval
        self.output_file = (
            Path(output_file)
            if output_file
            else self.output_dir / f"{site_name}.csv"
        )
        self.last_status_code: Optional[int] = None

    def fetch_html(self, url: str) -> Optional[str]:
        """发送GET请求，失败时按1/2/3秒重试，最终失败返回None。"""
        self.last_status_code = None
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.get(url, headers=self.HEADERS, timeout=self.TIMEOUT)
                self.last_status_code = response.status_code
                if response.status_code == 200:
                    # 部分站点未声明 charset，requests 会误判为 ISO-8859-1
                    if response.encoding is None or response.encoding.lower() == "iso-8859-1":
                        response.encoding = response.apparent_encoding or "utf-8"
                    return response.text
                print(f"[错误] 第{attempt + 1}次请求状态码异常：{response.status_code}，URL：{url}")
            except requests.exceptions.Timeout:
                print(f"[错误] 第{attempt + 1}次请求超时（{self.TIMEOUT}秒），URL：{url}")
            except requests.exceptions.ConnectionError:
                print(f"[错误] 第{attempt + 1}次请求连接失败，URL：{url}")
            except requests.exceptions.RequestException as exc:
                print(f"[错误] 第{attempt + 1}次请求发生异常：{exc}，URL：{url}")

            if attempt < self.max_retries:
                time.sleep(attempt + 1)

        print(f"[错误] 已重试{self.max_retries}次仍失败，放弃请求：{url}")
        return None

    @staticmethod
    def _extract_field(item, field: Dict, page_url: str) -> str:
        """按配置提取一个字段，缺失时返回空字符串。"""
        selector = field.get("selector", "")
        kind = field.get("kind", "text")
        if not selector:
            return ""

        tags = item.select(selector)
        if not tags:
            return ""

        if kind == "text":
            return tags[0].get_text(strip=True)

        if kind == "title":
            return (tags[0].get("title") or tags[0].get_text(strip=True)).strip()

        if kind == "href":
            href = (tags[0].get("href") or "").strip()
            return urljoin(page_url, href) if href else ""

        if kind == "text_all":
            values = [tag.get_text(strip=True) for tag in tags]
            return " / ".join(value for value in values if value)

        return tags[0].get_text(strip=True)

    def parse_page(self, html: str, page_url: str) -> List[Dict[str, str]]:
        """按配置解析当前页，返回列表嵌套字典。"""
        soup = BeautifulSoup(html, "html.parser")
        records: List[Dict[str, str]] = []
        item_selector = self.config.get("item_selector", "")

        for item in soup.select(item_selector):
            try:
                record = {}
                for field in self.config.get("fields", []):
                    record[field["label"]] = self._extract_field(item, field, page_url)
                records.append(record)
            except Exception as exc:
                print(f"[警告] 单条数据解析失败，已跳过：{exc}")

        return records

    def _get_next_page_url(self, html: str, page_url: str) -> Optional[str]:
        """优先使用 next_selector，再兼容分页文本。"""
        soup = BeautifulSoup(html, "html.parser")

        next_selector = self.config.get("next_selector", "")
        if next_selector:
            next_tag = soup.select_one(next_selector)
            if next_tag is not None:
                href = (next_tag.get("href") or "").strip()
                if href:
                    return urljoin(page_url, href)

        pager_selector = self.config.get("pager_selector", "")
        pager_texts = self.config.get("pager_texts", [])
        if pager_selector:
            for link in soup.select(pager_selector):
                if link.get_text(strip=True) in pager_texts:
                    href = (link.get("href") or "").strip()
                    if href:
                        return urljoin(page_url, href)

        return None

    def save_data(self, records: List[Dict[str, str]]) -> None:
        """按配置的字段顺序保存 CSV，编码 utf-8-sig。"""
        columns = [field["label"] for field in self.config.get("fields", [])]
        df = pd.DataFrame(records, columns=columns)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(self.output_file, index=False, encoding="utf-8-sig")

    def run(self) -> List[Dict[str, str]]:
        """主流程：请求、解析、翻页、保存。"""
        all_records: List[Dict[str, str]] = []
        page_url: Optional[str] = self.config.get("start_url", "")
        visited = set()
        page_no = 0

        print(f"\n===== 开始抓取：{self.config.get('name', self.site_name)} =====")

        while page_url and page_url not in visited:
            if self.max_pages and page_no >= self.max_pages:
                break

            visited.add(page_url)
            page_no += 1

            if page_no > 1:
                time.sleep(self.page_interval)

            print(f"正在抓取第{page_no}页：{page_url}")
            html = self.fetch_html(page_url)
            if html is None:
                print(f"[错误] 第{page_no}页获取失败，停止抓取")
                break

            records = self.parse_page(html, page_url)
            all_records.extend(records)
            print(f"第{page_no}页解析到 {len(records)} 条数据")

            page_url = self._get_next_page_url(html, page_url)

        self.save_data(all_records)
        print(f"{self.config.get('name', self.site_name)} 抓取完成，共 {len(all_records)} 条，已保存至 {self.output_file}")
        return all_records


def load_sites(config_path: Path) -> Dict:
    """加载 sites.json，返回站点配置字典。"""
    if not config_path.exists():
        raise FileNotFoundError(f"找不到配置文件：{config_path}")
    with config_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict) or not data:
        raise ValueError("sites.json 必须是非空对象")
    return data


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="配置驱动的通用静态列表页爬虫（一次运行一个站点）")
    parser.add_argument("--config", default=str(base_dir / "sites.json"), help="站点配置文件路径")
    parser.add_argument("--list", action="store_true", help="列出所有已配置站点")
    parser.add_argument("--site", help="要抓取的站点名；先用 --list 查看")
    parser.add_argument("--pages", type=int, default=0, help="最多抓几页；0 表示抓取全部页面")
    parser.add_argument("--output", default=None, help="CSV 输出路径；默认 universal_output/<site>.csv")
    parser.add_argument("--output-dir", default=str(base_dir / "universal_output"), help="默认输出目录")
    args = parser.parse_args()

    sites = load_sites(Path(args.config))

    if args.list:
        print("已配置站点：")
        for name, config in sites.items():
            print(f"  {name:10s} {config.get('name', ''):20s} {config.get('start_url', '')}")
        return

    if not args.site:
        print("请用 --site 指定一个站点；先运行 --list 查看可选站点。")
        print("示例：python universal_crawler.py --site cnblogs --output result.csv")
        return

    if args.site not in sites:
        print(f"未知站点：{args.site}")
        print("可选站点：" + "、".join(sites.keys()))
        return

    max_pages = None if args.pages <= 0 else args.pages
    crawler = UniversalCrawler(
        site_name=args.site,
        config=sites[args.site],
        output_dir=args.output_dir,
        output_file=args.output,
        max_pages=max_pages,
    )
    crawler.run()


if __name__ == "__main__":
    main()
