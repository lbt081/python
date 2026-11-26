# -*- coding: utf-8 -*-
"""一键运行全部 5 个任务，便于演示和截图。

运行：
    python run_all.py
"""

from __future__ import annotations

import runpy
import sys
import time

TASKS = [
    ("任务1　切片删除深度探究", "task1_slice_delete.py"),
    ("任务2　嵌套容器与可哈希辨析", "task2_hash_probe.py"),
    ("任务3　集合运算与集合推导式", "task3_set_ops.py"),
    ("任务4　去重算法对比", "task4_dedup.py"),
    ("任务5　综合设计：选课统计", "task5_course_stats.py"),
]

BANNER = "#" * 62


def main() -> int:
    print(BANNER)
    print("# Python 列表、元组、集合 实验")
    print("# 刘宝廷　3242052051028　软工24-2班")
    print(f"# Python {sys.version.split()[0]}　|　共 {len(TASKS)} 个任务")
    print(BANNER)

    started = time.perf_counter()
    for index, (title, filename) in enumerate(TASKS, start=1):
        print(f"\n\n{'*' * 62}")
        print(f"* 开始执行 {index}/{len(TASKS)}：{title}")
        print(f"{'*' * 62}")
        runpy.run_path(filename, run_name="__main__")

    elapsed = time.perf_counter() - started
    print(f"\n\n{BANNER}")
    print(f"# 全部 {len(TASKS)} 个任务执行完毕，总耗时 {elapsed:.2f} 秒")
    print(BANNER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
