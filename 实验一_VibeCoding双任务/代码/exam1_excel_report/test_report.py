# -*- coding: utf-8 -*-
"""Excel 报表脚本的 pytest 测试用例。

运行方式：
    cd exam1_excel_report
    pytest test_report.py -v
"""

import sys
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

# 保证从任意工作目录运行 pytest 时都能导入同目录的 main.py
sys.path.insert(0, str(Path(__file__).resolve().parent))

from main import (  # noqa: E402
    calculate_total,
    clean_sales_data,
    export_report,
    stats_by_region,
    stats_by_salesperson,
)


def make_valid_sales_df() -> pd.DataFrame:
    """构造 10 条有效销售数据，便于精确断言统计结果。"""
    return pd.DataFrame(
        [
            ["2026-03-01", "张三", "A", 2, 100.0, "华南"],
            ["2026-03-02", "张三", "B", 1, 50.0, "华南"],
            ["2026-03-03", "李四", "C", 3, 20.0, "华东"],
            ["2026-03-04", "李四", "D", 2, 30.0, "华东"],
            ["2026-03-05", "王五", "E", 1, 200.0, "华北"],
            ["2026-03-06", "王五", "F", 4, 25.0, "华北"],
            ["2026-03-07", "张三", "G", 1, 80.0, "华南"],
            ["2026-03-08", "李四", "H", 2, 40.0, "华东"],
            ["2026-03-09", "王五", "I", 3, 10.0, "华北"],
            ["2026-03-10", "张三", "J", 5, 20.0, "华南"],
        ],
        columns=["日期", "销售员", "产品", "数量", "单价", "地区"],
    )


def test_clean_valid_data_keeps_all_rows():
    """正常用例：10 条有效数据清洗后应全部保留。"""
    cleaned = clean_sales_data(make_valid_sales_df())

    assert len(cleaned) == 10
    assert list(cleaned.columns) == ["日期", "销售员", "产品", "数量", "单价", "地区"]
    assert cleaned["销售员"].value_counts().to_dict() == {"张三": 4, "李四": 3, "王五": 3}


def test_stats_and_total_are_correct():
    """正常用例：销售员、地区汇总与总销售额数值准确。"""
    cleaned = clean_sales_data(make_valid_sales_df())

    by_person = stats_by_salesperson(cleaned)
    assert list(by_person.columns) == ["销售员", "销售额"]
    assert by_person["销售员"].tolist() == ["张三", "王五", "李四"]
    assert by_person["销售额"].tolist() == pytest.approx([430.0, 330.0, 200.0])

    by_region = stats_by_region(cleaned)
    assert list(by_region.columns) == ["地区", "销售额"]
    assert by_region["地区"].tolist() == ["华南", "华北", "华东"]
    assert by_region["销售额"].tolist() == pytest.approx([430.0, 330.0, 200.0])

    assert calculate_total(cleaned) == pytest.approx(960.0)
    # 两种汇总口径必须与总销售额一致
    assert by_person["销售额"].sum() == pytest.approx(960.0)
    assert by_region["销售额"].sum() == pytest.approx(960.0)


def test_export_report_contains_four_sheets(tmp_path):
    """正常用例：导出的 xlsx 必须包含 4 个指定名称的工作表。"""
    cleaned = clean_sales_data(make_valid_sales_df())
    by_person = stats_by_salesperson(cleaned)
    by_region = stats_by_region(cleaned)
    total = calculate_total(cleaned)

    output = tmp_path / "report.xlsx"
    export_report(cleaned, by_person, by_region, total, str(output))

    assert output.exists()

    workbook = load_workbook(output, read_only=True)
    try:
        assert workbook.sheetnames == ["明细清洗后", "按销售员", "按地区", "总览"]

        summary_rows = list(workbook["总览"].values)
        assert summary_rows[0][0] == "月度总销售额"
        assert summary_rows[1][0] == pytest.approx(960.0)

        detail_rows = list(workbook["明细清洗后"].values)
        assert len(detail_rows) == 11  # 1 行表头 + 10 条明细
    finally:
        workbook.close()


def test_dirty_data_is_cleaned_by_rules():
    """边界用例 1：空值、负数量、完全重复行按规则清洗。"""
    dirty = pd.DataFrame(
        [
            ["2026-03-01", "张三", "A", 2, 100.0, "华南"],       # 有效
            ["2026-03-01", "张三", "A", 2, 100.0, "华南"],       # 完全重复
            ["2026-03-02", None, "B", 1, 50.0, "华南"],          # 销售员为空
            ["2026-03-03", "李四", "C", -3, 20.0, "华东"],       # 负数量
            ["2026-03-04", "王五", "D", 1, None, "华北"],        # 单价为空
            ["2026-03-05", "王五", "E", 1, 60.0, "华北"],        # 有效
        ],
        columns=["日期", "销售员", "产品", "数量", "单价", "地区"],
    )

    cleaned = clean_sales_data(dirty)

    assert len(cleaned) == 2
    assert cleaned["销售员"].tolist() == ["张三", "王五"]
    assert cleaned["产品"].tolist() == ["A", "E"]
    assert cleaned["数量"].tolist() == [2, 1]
    assert calculate_total(cleaned) == pytest.approx(260.0)


def test_all_invalid_rows_raise_error():
    """边界用例 2：全部数据无效时抛出“清洗后无有效数据”。"""
    invalid = pd.DataFrame(
        [
            ["2026-03-01", None, "A", 2, 100.0, "华南"],
            ["2026-03-02", "李四", "B", 0, 50.0, "华东"],
            ["2026-03-03", "王五", "C", -1, 20.0, "华北"],
        ],
        columns=["日期", "销售员", "产品", "数量", "单价", "地区"],
    )

    with pytest.raises(ValueError, match="清洗后无有效数据"):
        clean_sales_data(invalid)


def test_missing_price_column_raises_error():
    """边界用例 3：缺少“单价”字段时抛出字段缺失异常。"""
    df = make_valid_sales_df().drop(columns=["单价"])

    with pytest.raises(ValueError) as exc_info:
        clean_sales_data(df)

    message = str(exc_info.value)
    assert "缺少字段" in message
    assert "单价" in message
    assert "日期" not in message
