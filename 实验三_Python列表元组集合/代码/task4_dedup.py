# -*- coding: utf-8 -*-
"""任务4：去重算法对比（无序去重 vs 保序去重）。

原始数据：data = [5,2,7,2,5,9,7,3,9,1]

运行：
    python task4_dedup.py
"""

from __future__ import annotations

import random
import timeit
from typing import List

LINE = "=" * 62

DATA = [5, 2, 7, 2, 5, 9, 7, 3, 9, 1]


def section(title: str) -> None:
    print(f"\n{LINE}\n{title}\n{LINE}")


def dedup_loop(data: List[int]) -> List[int]:
    """方案2：手写保序去重，元素第一次出现的位置保留。"""
    result: List[int] = []
    for item in data:
        if item not in result:
            result.append(item)
    return result


def dedup_seen_set(data: List[int]) -> List[int]:
    """方案2 优化版：用辅助 set 把查找从 O(n) 降到 O(1)。"""
    result: List[int] = []
    seen: set = set()
    for item in data:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def task4_dedup() -> None:
    section("任务4-1　原始数据")
    print(f"data = {DATA}")
    print(f"长度：{len(DATA)}，去重后应为：{sorted(set(DATA))}，共 {len(set(DATA))} 个")

    section("任务4-2　方案1：list(set(data)) 无序去重")
    result_set = list(set(DATA))
    print(f"结果：{result_set}")
    print("问题：元素顺序由哈希表决定，与原始顺序无关。")
    print("注意：本例都是小整数，哈希值等于自身，所以看起来像升序；")
    print("      这只是 CPython 对小整数的实现细节，不能当作稳定规律。")

    section("任务4-3　方案2：手写保序去重")
    result_loop = dedup_loop(DATA)
    print(f"结果：{result_loop}")
    print(f"是否保持原始顺序：{result_loop == [5, 2, 7, 9, 3, 1]}")

    section("任务4-4　方案3：dict.fromkeys 一行保序去重")
    result_dict = list(dict.fromkeys(DATA))
    print(f"结果：{result_dict}")
    print("原理：dict 的 key 唯一且保持插入顺序，fromkeys 依次写入即完成去重。")

    section("任务4-5　三种方案结果对照")
    print(f"{'方案':<32}{'结果'}")
    print("-" * 78)
    print(f"{'list(set(data))':<32}{result_set}")
    print(f"{'手写循环判断':<32}{result_loop}")
    print(f"{'辅助 set 优化':<32}{dedup_seen_set(DATA)}")
    print(f"{'list(dict.fromkeys(data))':<32}{result_dict}")

    section("任务4-6　顺序稳定性实验：换一组数据验证")
    random.seed(7)
    sample = [random.randint(1, 30) for _ in range(12)]
    print(f"随机样本：{sample}")
    print(f"set 去重结果：{list(set(sample))}")
    print(f"保序去重结果：{dedup_loop(sample)}")
    print(f"两者元素集合是否相同：{set(sample) == set(dedup_loop(sample))}")
    print(f"两者顺序是否相同：{list(set(sample)) == dedup_loop(sample)}")

    section("任务4-7　性能对比（2 万条数据，重复率约 50%）")
    random.seed(42)
    big = [random.randint(1, 10000) for _ in range(20000)]

    t_set = min(timeit.repeat(lambda: list(set(big)), number=1, repeat=5))
    t_loop = min(timeit.repeat(lambda: dedup_loop(big), number=1, repeat=5))
    t_seen = min(timeit.repeat(lambda: dedup_seen_set(big), number=1, repeat=5))
    t_dict = min(timeit.repeat(lambda: list(dict.fromkeys(big)), number=1, repeat=5))

    print(f"{'方案':<28}{'单次耗时（秒）':<16}{'说明'}")
    print("-" * 74)
    print(f"{'list(set(...))':<28}{t_set:<16.5f}不保序，最快")
    print(f"{'手写循环 in list':<28}{t_loop:<16.5f}O(n²)，数据一大就慢")
    print(f"{'辅助 set 判断':<28}{t_seen:<16.5f}O(n)，保序且快")
    print(f"{'dict.fromkeys':<28}{t_dict:<16.5f}最短写法，性能接近 set")

    section("任务4-8　优缺点小结")
    rows = [
        ("list(set(data))", "一行完成，速度最快", "丢失原始顺序，元素必须可哈希"),
        ("手写循环 + in 判断", "不要求元素可哈希，逻辑直观", "O(n²)，大数据慢"),
        ("辅助 set 优化", "O(n) 且保序", "需要额外内存，元素需可哈希"),
        ("dict.fromkeys", "最短且保序，性能好", "元素需可哈希"),
    ]
    print(f"{'方案':<22}{'优点':<26}{'缺点'}")
    print("-" * 88)
    for name, pro, con in rows:
        print(f"{name:<22}{pro:<26}{con}")

    print("\n任务4 结论：")
    print("  1. 只要顺序无关且元素可哈希，用 list(set(data)) 最省事；")
    print("  2. 需要保留首次出现顺序时，优先 list(dict.fromkeys(data))；")
    print("  3. 元素不可哈希时，只能手写循环或转换后可哈希再处理。")


if __name__ == "__main__":
    task4_dedup()
