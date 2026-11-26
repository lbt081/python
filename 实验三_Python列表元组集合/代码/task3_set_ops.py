# -*- coding: utf-8 -*-
"""任务3：集合全部运算与集合推导式。

A = {2,4,6,8,10,12}，B = {3,6,9,12,15}

运行：
    python task3_set_ops.py
"""

from __future__ import annotations

LINE = "=" * 62

A = {2, 4, 6, 8, 10, 12}
B = {3, 6, 9, 12, 15}


def section(title: str) -> None:
    print(f"\n{LINE}\n{title}\n{LINE}")


def line(name: str, symbol: str, result: set, note: str) -> None:
    print(f"{name:<10}{symbol:<4}{str(sorted(result)):<40}{note}")


def task3_set_ops() -> None:
    section("任务3-1　五个集合运算")
    print(f"A = {A}")
    print(f"B = {B}")
    print()
    print(f"{'运算':<10}{'符号':<4}{'结果':<40}{'含义'}")
    print("-" * 96)
    line("交集", "&", A & B, "同时属于 A 和 B")
    line("并集", "|", A | B, "属于 A 或属于 B")
    line("差集", "-", A - B, "属于 A 但不属于 B")
    line("差集", "-", B - A, "属于 B 但不属于 A")
    line("对称差", "^", A ^ B, "只属于其中一个集合")

    section("任务3-2　方法调用写法与运算符写法等价")
    pairs = [
        ("intersection", A.intersection(B), A & B),
        ("union", A.union(B), A | B),
        ("difference", A.difference(B), A - B),
        ("symmetric_difference", A.symmetric_difference(B), A ^ B),
    ]
    for name, by_method, by_operator in pairs:
        same = by_method == by_operator
        print(f"A.{name}(B) == A 运算符 B ? {same}")

    section("任务3-3　集合推导式：1~30 中能被 4 整除的数字")
    divisible_by_4 = {x for x in range(1, 31) if x % 4 == 0}
    print(f"结果：{sorted(divisible_by_4)}")
    print(f"元素个数：{len(divisible_by_4)}")

    even_square = {x * x for x in range(1, 11) if x % 2 == 0}
    print(f"拓展·1~10 中偶数的平方：{sorted(even_square)}")

    words = ["apple", "Banana", "apple", "cherry", "banana"]
    lower_set = {word.lower() for word in words}
    print(f"拓展·单词统一小写去重：{sorted(lower_set)}")

    section("任务3-4　集合运算的典型用途：名单比对")
    all_students = {"张三", "李四", "王五", "赵六", "钱七"}
    submitted = {"李四", "王五", "钱七"}
    missing = all_students - submitted
    extra = submitted - all_students
    print(f"应交名单：{sorted(all_students)}")
    print(f"已交名单：{sorted(submitted)}")
    print(f"未交名单：{sorted(missing)}")
    print(f"名单外的人：{sorted(extra) if extra else '无'}")
    print(f"交齐了吗：{'是' if not missing else '否'}")

    section("任务3-5　集合运算的两个注意点")
    empty = set()
    print(f"空集合必须写 set()，写 {{}} 得到的是字典：type({{}}) = {type({}).__name__}")

    left = {1, 2, 3}
    right = {2, 3, 4}
    print(f"运算符写法生成新集合，原集合不变：left = {left}，right = {right}")
    left &= right
    print(f"增强赋值会原地修改：left &= right 之后 left = {left}")

    print("\n任务3 结论：")
    print("  1. & | - ^ 四种运算分别对应交、并、差、对称差，方法写法与运算符等价；")
    print("  2. 差集有方向，A-B 与 B-A 结果不同；")
    print("  3. 集合推导式语法与列表推导式一致，只是用花括号，结果自动去重。")


if __name__ == "__main__":
    task3_set_ops()
