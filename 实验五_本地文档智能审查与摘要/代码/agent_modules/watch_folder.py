# -*- coding: utf-8 -*-
"""模块三：用 watchdog 监控文件夹，新文件放入后自动触发分析流程。

作用：
    监控指定文件夹（含子目录），当有新的 .txt/.md 文件创建或移动进来时，
    等待文件写入稳定，然后自动执行“读取 → 分词统计 → 词云 → 报告”流程，
    实现无人值守的文档分析。

运行示例（在项目根目录执行）：
    python agent_modules/watch_folder.py --folder "示例文本" --debounce 2
    python agent_modules/watch_folder.py --folder "示例文本" --run-on-start
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError as exc:
    raise ImportError("未安装 watchdog，请先执行：pip install watchdog") from exc

# 让本模块可以导入项目根目录下的 batch_read_text.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from batch_read_text import analyze_texts, generate_wordcloud, write_report
except ImportError as exc:
    raise ImportError(
        "无法导入 batch_read_text.py，请确保它与 agent_modules 目录在同一项目根目录"
    ) from exc


# 这些文件是控制文件或分析输出，不能触发新的一轮分析，否则会形成死循环
IGNORED_NAMES = {
    "document_analysis_report.txt",
    "document_wordcloud.png",
    "llm_review.md",
    "llm_prompt.txt",
    "user_dict.txt",
    "stopwords.txt",
}

# 编辑器临时文件后缀
IGNORED_SUFFIXES = {".tmp", ".swp", ".part", ".bak"}


def now_text() -> str:
    """返回当前时间字符串，用于日志。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def is_target_file(path: Path) -> bool:
    """判断文件是否是本次需要监控的 .txt/.md 文件。"""
    name = path.name
    if name in IGNORED_NAMES:
        return False
    if name.startswith(".") or name.startswith("~$"):
        return False
    if path.suffix.lower() not in {".txt", ".md"}:
        return False
    if path.suffix.lower() in IGNORED_SUFFIXES:
        return False
    return True


def wait_until_stable(
    path: Path,
    timeout: float = 10.0,
    interval: float = 0.5,
) -> bool:
    """
    等待文件大小连续两次不变，尽量确保复制/写入已经完成。

    参数：
        path：待检查文件。
        timeout：最长等待秒数。
        interval：检查间隔秒数。

    返回：
        文件稳定返回 True；文件消失、无权限或超时返回 False。
    """
    start = time.time()
    last_size: int | None = None

    while time.time() - start < timeout:
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return False
        except OSError as exc:
            print(f"[提示] 无法读取文件状态：{path}，原因：{exc}")
            return False

        if size == last_size:
            return True

        last_size = size
        time.sleep(interval)

    return False


def run_pipeline(
    folder: Path,
    user_dict_path: Path | None,
    stopwords_path: Path | None,
) -> None:
    """
    执行一次完整分析流程。

    参数：
        folder：被监控的文件夹。
        user_dict_path：自定义词典路径，可为 None。
        stopwords_path：停用词表路径，可为 None。
    """
    report_path = folder / "document_analysis_report.txt"
    wordcloud_path = folder / "document_wordcloud.png"

    # 排除控制文件和输出文件，避免它们参与分词或触发递归分析
    exclude_paths = {
        report_path,
        wordcloud_path,
        folder / "user_dict.txt",
        folder / "stopwords.txt",
        folder / "llm_review.md",
        folder / "llm_prompt.txt",
    }

    result = analyze_texts(
        folder_path=folder,
        user_dict_path=user_dict_path,
        stopwords_path=stopwords_path,
        global_top_n=50,
        file_top_n=10,
        exclude_paths=exclude_paths,
    )

    generate_wordcloud(
        result.global_top,
        output_path=wordcloud_path,
        show=False,  # 无人值守模式不弹窗
    )

    report_file = write_report(result, output_path=report_path)

    print(
        f"[完成] {now_text()} 分析结束："
        f"成功文件 {sum(1 for s in result.file_statuses if s.status == '成功')} 个，"
        f"有效词汇 {result.total_words} 个，"
        f"报告：{report_file or '未生成'}"
    )


class TextFileHandler(FileSystemEventHandler):
    """监听新建和移入的 .txt/.md 文件，并做防抖处理。"""

    def __init__(
        self,
        folder: Path,
        user_dict_path: Path | None,
        stopwords_path: Path | None,
        debounce: float = 2.0,
    ) -> None:
        super().__init__()
        self.folder = folder
        self.user_dict_path = user_dict_path
        self.stopwords_path = stopwords_path
        self.debounce = debounce

        self._timer: threading.Timer | None = None
        self._timer_lock = threading.Lock()
        self._analysis_lock = threading.Lock()
        self._last_path: Path | None = None

    def on_created(self, event) -> None:
        """文件创建事件。"""
        if not event.is_directory:
            self._schedule(Path(event.src_path))

    def on_moved(self, event) -> None:
        """文件移动事件：处理从其他目录移动进来的文件或文件夹。"""
        if event.is_directory:
            # 整个文件夹被移动进来时，Watchdog 可能只报告目录事件，
            # 这里主动扫描一次，发现其中的文本文件后触发分析。
            moved_dir = Path(event.dest_path)
            try:
                for path in moved_dir.rglob("*"):
                    if path.is_file() and is_target_file(path):
                        self._schedule(path)
                        break
            except (OSError, RuntimeError) as exc:
                print(f"[提示] 扫描移入目录失败：{moved_dir}，原因：{exc}")
            return

        self._schedule(Path(event.dest_path))

    def _schedule(self, path: Path) -> None:
        """防抖：短时间内多个文件事件只触发一次分析。"""
        if not is_target_file(path):
            return

        print(f"[事件] {now_text()} 检测到新文件：{path}")

        with self._timer_lock:
            self._last_path = path

            if self._timer is not None:
                self._timer.cancel()

            self._timer = threading.Timer(self.debounce, self._run_analysis)
            self._timer.daemon = True
            self._timer.start()

    def _run_analysis(self) -> None:
        """在后台线程中执行分析，使用锁保证不会并发运行。"""
        with self._analysis_lock:
            if self._last_path is not None and not wait_until_stable(self._last_path):
                print(f"[跳过] 文件仍在写入或已消失：{self._last_path}")
                return

            print(f"\n[{now_text()}] 开始自动分析...")
            try:
                run_pipeline(
                    self.folder,
                    self.user_dict_path,
                    self.stopwords_path,
                )
            except Exception as exc:
                # 单次分析失败不能导致监控线程退出
                print(f"[错误] 自动分析失败：{exc}")


def main() -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="监控文件夹并自动分析新增文本")
    parser.add_argument("--folder", required=True, help="要监控的文件夹")
    parser.add_argument("--debounce", type=float, default=2.0, help="防抖等待秒数，默认 2")
    parser.add_argument("--user-dict", default=None, help="自定义词典路径")
    parser.add_argument("--stopwords", default=None, help="停用词表路径")
    parser.add_argument("--no-recursive", action="store_true", help="只监控当前目录，不监控子目录")
    parser.add_argument("--run-on-start", action="store_true", help="启动时先分析一次现有文件")
    args = parser.parse_args()

    folder = Path(args.folder).expanduser()
    if not folder.is_dir():
        print(f"[错误] 目标文件夹不存在或不是文件夹：{folder}")
        return 1

    # 未显式指定时，自动使用目录中的 user_dict.txt / stopwords.txt
    user_dict_path = (
        Path(args.user_dict).expanduser()
        if args.user_dict
        else (folder / "user_dict.txt" if (folder / "user_dict.txt").is_file() else None)
    )
    stopwords_path = (
        Path(args.stopwords).expanduser()
        if args.stopwords
        else (folder / "stopwords.txt" if (folder / "stopwords.txt").is_file() else None)
    )

    print("=" * 60)
    print("文件夹自动监控")
    print(f"监控目录：{folder}")
    print(f"递归子目录：{'否' if args.no_recursive else '是'}")
    print(f"自定义词典：{user_dict_path or '未使用'}")
    print(f"停用词表：{stopwords_path or '未使用'}")
    print("按 Ctrl+C 停止监控。")
    print("=" * 60)

    if args.run_on_start:
        print(f"\n[{now_text()}] 启动时先分析一次...")
        try:
            run_pipeline(folder, user_dict_path, stopwords_path)
        except Exception as exc:
            print(f"[错误] 启动分析失败：{exc}")

    handler = TextFileHandler(
        folder=folder,
        user_dict_path=user_dict_path,
        stopwords_path=stopwords_path,
        debounce=args.debounce,
    )

    observer = Observer()
    try:
        observer.schedule(
            handler,
            str(folder),
            recursive=not args.no_recursive,
        )
        observer.start()
    except Exception as exc:
        print(f"[错误] 启动文件夹监控失败：{exc}")
        return 1

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n[{now_text()}] 收到停止信号，正在退出...")
    finally:
        observer.stop()
        observer.join()

    print(f"[完成] {now_text()} 监控已停止。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
