# -*- coding: utf-8 -*-
"""任务5：综合设计——两份学生选课编号的统计。

class1 = [101,103,105,107,109,103,101]
class2 = [102,104,106,108,109,107,102]

运行：
    python task5_course_stats.py
"""

from __future__ import annotations

from typing import List

LINE = "=" * 62

CLASS1: List[int] = [101, 103, 105, 107, 109, 103, 101]
CLASS2: List[int] = [102, 104, 106, 108, 109, 107, 102]


def section(title: str) -> None:
    print(f"\n{LINE}\n{title}\n{LINE}")


def ordered_unique(data: List[int]) -> List[int]:
    """保序去重，保留每个学号第一次出现的顺序。"""
    return list(dict.fromkeys(data))


def task5_course() -> None:
    section("任务5-0　原始数据")
    print(f"1 班选课编号：{CLASS1}，共 {len(CLASS1)} 条记录")
    print(f"2 班选课编号：{CLASS2}，共 {len(CLASS2)} 条记录")
    print("观察：两个列表都有重复学号，需要先去重再统计。")

    section("任务5-①　分别获取两个班不重复的学号（保序）")
    unique1 = ordered_unique(CLASS1)
    unique2 = ordered_unique(CLASS2)
    print(f"1 班去重结果：{unique1}，人数 {len(unique1)}")
    print(f"2 班去重结果：{unique2}，人数 {len(unique2)}")
    print("说明：用 dict.fromkeys 保证输出顺序与第一次出现顺序一致，")
    print("      如果直接 set() 先转再转回列表，顺序就不可控了。")

    set1 = set(unique1)
    set2 = set(unique2)

    section("任务5-②　同时选两门课的学生（交集）")
    both = set1 & set2
    print(f"set1 = {sorted(set1)}")
    print(f"set2 = {sorted(set2)}")
    print(f"交集 = {sorted(both)}，共 {len(both)} 人")
    print("说明：交集里的人既出现在 1 班名单，也出现在 2 班名单。")

    section("任务5-③　只选其中一门课的学生（对称差）")
    only_one = set1 ^ set2
    print(f"对称差 = {sorted(only_one)}，共 {len(only_one)} 人")
    print("验证：交集人数 + 对称差人数 =", len(both) + len(only_one),
          f"，等于两班去重后总人数 {len(set1 | set2)}")

    section("任务5-④　选了 1 班但没选 2 班的学生（差集）")
    only_class1 = set1 - set2
    only_class2 = set2 - set1
    print(f"1 班独有 = {sorted(only_class1)}，共 {len(only_class1)} 人")
    print(f"2 班独有 = {sorted(only_class2)}，共 {len(only_class2)} 人")
    print(f"校验：两个独有部分合并起来正好等于对称差 → "
          f"{only_class1 | only_class2 == only_one}")

    section("任务5-⑤　把交集结果转为元组")
    both_tuple = tuple(sorted(both))
    print(f"交集集合：{sorted(both)}，type = {type(both).__name__}")
    print(f"转成元组：{both_tuple}，type = {type(both_tuple).__name__}")
    print("为什么可以转元组：集合和元组都只要求元素可哈希，")
    print("                    学号是 int，本身可哈希，所以能互相转换。")
    print("为什么还能放进集合：元组不可变，哈希值固定，可以继续作为集合元素。")

    nested = {tuple(sorted(both)), tuple(sorted(only_class1))}
    print(f"把两个元组放进集合：{nested}")

    section("任务5-⑥　一份完整的统计汇总表")
    print(f"{'项目':<24}{'人数':<8}{'学号'}")
    print("-" * 72)
    print(f"{'1 班去重后':<24}{len(unique1):<8}{unique1}")
    print(f"{'2 班去重后':<24}{len(unique2):<8}{unique2}")
    print(f"{'两班都选（交集）':<24}{len(both):<8}{sorted(both)}")
    print(f"{'只选一门（对称差）':<24}{len(only_one):<8}{sorted(only_one)}")
    print(f"{'只选 1 班（差集）':<24}{len(only_class1):<8}{sorted(only_class1)}")
    print(f"{'只选 2 班（差集）':<24}{len(only_class2):<8}{sorted(only_class2)}")
    print(f"{'两班总人数（并集）':<24}{len(set1 | set2):<8}{sorted(set1 | set2)}")

    section("任务5-拓展　嵌套列表去重")
    nest = [[1, 2], [3, 4], [1, 2], [5, 6]]
    print(f"原始嵌套列表：{nest}")
    try:
        set(nest)
    except TypeError as exc:
        print(f"直接 set(nest) 失败：{type(exc).__name__}: {exc}")
        print("原因：内层 list 不可哈希。")

    seen: set = set()
    deduped: List[List[int]] = []
    for item in nest:
        key = tuple(item)
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    print(f"转元组去重后再转回列表：{deduped}")

    one_line = [list(t) for t in dict.fromkeys(tuple(item) for item in nest)]
    print(f"一行写法：{one_line}")
    print("说明：先去重（内层转元组），再按需转回列表，保持了原始顺序。")

    print("\n任务5 结论：")
    print("  1. 统计前先去重，否则重复学号会让人数虚高；")
    print("  2. 交集看共同选课，对称差看只选一门，差集看单边独有；")
    print("  3. 集合元素必须可哈希，所以嵌套列表要先转元组再参与集合运算。")


if __name__ == "__main__":
    task5_course()
