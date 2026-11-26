# -*- coding: utf-8 -*-
"""任务1：切片删除深度探究。

核心结论：del 列表[切片] 先按“删除前的原始索引”一次性算出要删的下标集合，
再统一删除；它不是边删边重新编号的动态过程。

运行：
    python task1_slice_delete.py
"""

from __future__ import annotations

from typing import List

LINE = "=" * 62


def section(title: str) -> None:
    print(f"\n{LINE}\n{title}\n{LINE}")


def show(name: str, before: List[int], after: List[int], expect: List[int]) -> None:
    """打印删除前后结果，并用 assert 自校验预判是否正确。"""
    status = "通过" if after == expect else "不一致"
    print(f"{name}")
    print(f"  删除前：{before}")
    print(f"  删除后：{after}")
    print(f"  预判值：{expect}　校验：{status}")
    assert after == expect, f"{name} 的实际结果与预判不一致"


def task1_slice_delete() -> None:
    section("任务1-1　del ls[::3]：从索引 0 开始，每 3 个删一个")

    # 索引：0 1 2 3 4 5 6 7 8 9，被删的是 0、3、6、9
    ls1 = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    before = ls1.copy()
    del ls1[::3]
    show("del ls1[::3]", before, ls1, [1, 2, 4, 5, 7, 8])

    section("任务1-2　del ls[1::3]：从索引 1 开始，每 3 个删一个")
    # 被删的是 1、4、7，剩下 0、2、3、5、6、8、9
    ls2 = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    before = ls2.copy()
    del ls2[1::3]
    show("del ls2[1::3]", before, ls2, [0, 2, 3, 5, 6, 8, 9])

    section("任务1-3　del ls[::-2]：负步长，从末尾往回每隔一个删一个")
    # 起点是最后一个元素索引 5，依次是 5、3、1，剩下 0、2、4
    ls3 = [0, 1, 2, 3, 4, 5]
    before = ls3.copy()
    del ls3[::-2]
    show("del ls3[::-2]", before, ls3, [0, 2, 4])

    section("任务1-4　拓展坑：for 循环里边遍历边删除")
    # 这个例子会“看起来正确”，但不是因为写法对，而是因为删除位置刚好错开
    ls4 = [1, 2, 3, 4, 5, 6]
    origin4 = ls4.copy()
    removed4 = []
    for value in ls4:
        if value % 2 == 0:
            ls4.remove(value)
            removed4.append(value)
    print(f"原始列表：{origin4}")
    print(f"循环中被删的元素：{removed4}")
    print(f"循环后结果：{ls4}")
    print("现象：这里偶数恰好全被删掉，属于“碰巧正确”。")

    # 换成连续偶数，问题立刻暴露：4 没有被删掉
    ls5 = [2, 4, 6, 8]
    origin5 = ls5.copy()
    removed5 = []
    for value in ls5:
        if value % 2 == 0:
            ls5.remove(value)
            removed5.append(value)
    print(f"\n原始列表：{origin5}")
    print(f"循环中被删的元素：{removed5}")
    print(f"循环后结果：{ls5}")
    print(f"漏删元素：{[x for x in ls5 if x % 2 == 0]}")

    section("任务1-5　三种安全写法")
    data = [2, 4, 5, 6, 8, 9]
    print(f"待处理列表：{data}，目标：删除所有偶数")
    print()

    safe1 = [x for x in data if x % 2 != 0]
    print(f"方案A 列表推导式生成新列表：{safe1}")

    safe2 = data.copy()
    for index in range(len(safe2) - 1, -1, -1):
        if safe2[index] % 2 == 0:
            safe2.pop(index)
    print(f"方案B 倒序遍历按下标删除：{safe2}")

    safe3 = data.copy()
    index = 0
    while index < len(safe3):
        if safe3[index] % 2 == 0:
            safe3.pop(index)
        else:
            index += 1
    print(f"方案C while 循环手动控制下标：{safe3}")
    print(f"三种方案结果一致：{safe1 == safe2 == safe3}")

    print("\n任务1 结论：")
    print("  1. 切片删除的下标在删除前一次性确定，与元素删掉后如何前移无关；")
    print("  2. 正步长从切片起点往后数，负步长先把起点解析为末尾再往前数；")
    print("  3. for 循环内部维护独立下标，删除元素会让后续元素前移，导致跳过元素；")
    print("  4. 想边遍历边删，优先用列表推导式生成新列表，或倒序遍历。")


if __name__ == "__main__":
    task1_slice_delete()
