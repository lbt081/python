# -*- coding: utf-8 -*-
"""任务2：嵌套容器与可哈希深度辨析。

判断规则：对象能否放进 set / 作为 dict 的 key，取决于它是否可哈希。
不可变是必要条件，但不是充分条件——元组本身不可变，只要里面装了 list，
整体仍然不可哈希。

运行：
    python task2_hash_probe.py
"""

from __future__ import annotations

from typing import Any

LINE = "=" * 62


def section(title: str) -> None:
    print(f"\n{LINE}\n{title}\n{LINE}")


def probe(bucket: set, value: Any, label: str, reason: str) -> None:
    """尝试把 value 放进集合，成功或报错都记录下来并说明原因。"""
    try:
        bucket.add(value)
        print(f"[成功] {label:<26} 加入后集合：{bucket}")
        print(f"       原因：{reason}")
    except TypeError as exc:
        print(f"[报错] {label:<26} {type(exc).__name__}: {exc}")
        print(f"       原因：{reason}")


def task2_hash() -> None:
    section("任务2-1　逐条测试能否加入集合")
    bucket: set = set()

    probe(
        bucket,
        (1, 2, 3),
        "add((1,2,3))",
        "元组内三个元素都是 int，int 可哈希，元组整体可哈希。",
    )
    probe(
        bucket,
        frozenset({1, 2}),
        "add(frozenset({1,2}))",
        "frozenset 是不可变集合，哈希值固定，可作为集合元素。",
    )
    probe(
        bucket,
        (1, [2, 3]),
        "add((1,[2,3]))",
        "元组内含有 list，list 可变且不可哈希，导致整个元组不可哈希。",
    )
    probe(
        bucket,
        [1, 2],
        "add([1,2])",
        "list 支持增删改，哈希值无法固定，Python 直接判定不可哈希。",
    )
    probe(
        bucket,
        {1, 2},
        "add({1,2})",
        "普通 set 可变，元素增删会改变哈希结果，所以 set 不能被嵌套。",
    )

    section("任务2-2　集合里放集合的正确写法：frozenset")
    nested = {frozenset({1, 2}), frozenset({2, 3}), frozenset({1, 2})}
    print(f"嵌套集合：{nested}")
    print(f"元素个数：{len(nested)}（重复的 frozenset({{1,2}}) 被自动去重）")

    matrix = {frozenset(row) for row in [(1, 2), (2, 3), (1, 2)]}
    print(f"用推导式生成：{matrix}")

    section("任务2-3　“引用不可变”不等于“内容不可变”")
    t = (1, [2, 3])
    print(f"原始元组：{t}，id(t[1]) = {id(t[1])}")
    t[1].append(4)
    print(f"执行 t[1].append(4) 之后：{t}")
    print(f"再次查看 id(t[1]) = {id(t[1])}")
    print("说明：元组保存的是引用地址，地址没变，所以元组本身没被修改；")
    print("      但列表是可变对象，它内部的内容可以继续变化。")
    print("      正因为内容可能变化，含 list 的元组不能保证哈希值稳定，因此不可哈希。")

    try:
        t[1] = [9]
    except TypeError as exc:
        print(f"\n对比：t[1] = [9] 会报 {type(exc).__name__}: {exc}")
        print("      这说明“元组元素不能被重新绑定”，才是元组不可变的真正含义。")

    section("任务2-4　可哈希判定速查")
    checks = [
        (1, "int"),
        ("abc", "str"),
        ((1, 2), "纯数字元组"),
        (frozenset({1}), "frozenset"),
        ([1], "list"),
        ({1}, "set"),
        ({"a": 1}, "dict"),
        ((1, [2]), "含 list 的元组"),
    ]
    print(f"{'对象':<16}{'类型说明':<14}{'可哈希':<8}")
    print("-" * 42)
    for value, label in checks:
        try:
            hash(value)
            flag = "是"
        except TypeError:
            flag = "否"
        print(f"{str(value):<16}{label:<14}{flag:<8}")

    print("\n任务2 结论：")
    print("  1. 可哈希要求对象生命周期内哈希值不变，可变容器 list / set / dict 都不可哈希；")
    print("  2. 元组是否可哈希取决于所有元素，任一元素不可哈希则整体不可哈希；")
    print("  3. 需要“集合里放集合”时，内层改用 frozenset。")


if __name__ == "__main__":
    task2_hash()
