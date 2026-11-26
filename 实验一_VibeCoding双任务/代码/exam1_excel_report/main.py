"""
Excel 销售报表生成脚本

功能：
    1. 读取销售原始数据 sales_raw.xlsx；
    2. 清洗空值、重复行、非法数量与无法转换的数值；
    3. 按销售员、地区、月度汇总销售额；
    4. 导出包含 4 个工作表的 Excel 报表。

默认路径：
    输入：./data/sales_raw.xlsx
    输出：./report.xlsx

用法：
    python main.py
    python main.py -i data/sales_raw.xlsx -o report.xlsx
"""

import argparse
import sys
from pathlib import Path

import pandas as pd


def clean_sales_data(df: pd.DataFrame) -> pd.DataFrame:
    """清洗销售原始数据，返回仅包含 6 个核心字段的有效数据。"""
    required_columns = ["日期", "销售员", "产品", "数量", "单价", "地区"]

    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"缺少字段：{'、'.join(missing_columns)}")

    data = df[required_columns].copy()
    data = data.replace(r"^\s*$", pd.NA, regex=True)
    data = data.dropna(subset=required_columns)

    data["数量"] = pd.to_numeric(data["数量"], errors="coerce")
    data["单价"] = pd.to_numeric(data["单价"], errors="coerce")
    data = data.dropna(subset=["数量", "单价"])

    data = data[data["数量"] > 0]
    data = data.drop_duplicates(subset=required_columns, keep="first")

    if data.empty:
        raise ValueError("清洗后无有效数据")

    return data.reset_index(drop=True)


def stats_by_salesperson(df: pd.DataFrame) -> pd.DataFrame:
    """按销售员汇总销售额，返回 [销售员, 销售额]，按销售额降序。"""
    data = df.copy()
    data["销售额"] = (data["数量"] * data["单价"]).round(2)

    result = (
        data.groupby("销售员", as_index=False)["销售额"]
        .sum()
        .round({"销售额": 2})
        .sort_values("销售额", ascending=False)
        .reset_index(drop=True)
    )
    return result[["销售员", "销售额"]]


def stats_by_region(df: pd.DataFrame) -> pd.DataFrame:
    """按地区汇总销售额，返回 [地区, 销售额]，按销售额降序。"""
    data = df.copy()
    data["销售额"] = (data["数量"] * data["单价"]).round(2)

    result = (
        data.groupby("地区", as_index=False)["销售额"]
        .sum()
        .round({"销售额": 2})
        .sort_values("销售额", ascending=False)
        .reset_index(drop=True)
    )
    return result[["地区", "销售额"]]


def calculate_total(df: pd.DataFrame) -> float:
    """计算全部数据的总销售额，返回保留 2 位小数的浮点数。"""
    amount = (df["数量"] * df["单价"]).round(2)
    return float(round(amount.sum(), 2))


def export_report(clean_df, salesperson_df, region_df, total, output_path):
    """将 4 类数据写入同一个 xlsx 文件的 4 个工作表。"""
    overview_df = pd.DataFrame({"月度总销售额": [float(total)]})
    amount_columns = {"单价", "销售额", "月度总销售额", "金额"}

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        clean_df.to_excel(writer, sheet_name="明细清洗后", index=False)
        salesperson_df.to_excel(writer, sheet_name="按销售员", index=False)
        region_df.to_excel(writer, sheet_name="按地区", index=False)
        overview_df.to_excel(writer, sheet_name="总览", index=False)

        sheet_frames = {
            "明细清洗后": clean_df,
            "按销售员": salesperson_df,
            "按地区": region_df,
            "总览": overview_df,
        }
        for sheet_name, frame in sheet_frames.items():
            worksheet = writer.sheets[sheet_name]
            for col_index, col_name in enumerate(frame.columns, start=1):
                if col_name in amount_columns:
                    for row_index in range(2, len(frame) + 2):
                        worksheet.cell(row=row_index, column=col_index).number_format = "0.00"

    print(f"报表已生成至 {output_path}")


def main() -> int:
    """解析命令行参数并执行完整流程，返回进程退出码。"""
    parser = argparse.ArgumentParser(description="Excel 销售数据清洗与报表生成脚本")
    parser.add_argument(
        "-i", "--input",
        default="./data/sales_raw.xlsx",
        help="输入 Excel 文件路径，默认 ./data/sales_raw.xlsx",
    )
    parser.add_argument(
        "-o", "--output",
        default="./report.xlsx",
        help="输出 Excel 文件路径，默认 ./report.xlsx",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print("错误：输入文件不存在，请检查路径")
        return 1

    try:
        df = pd.read_excel(input_path, engine="openpyxl")
    except Exception:
        print("错误：无法读取 Excel 文件，文件可能为空或已损坏")
        return 1

    try:
        clean_df = clean_sales_data(df)
        salesperson_df = stats_by_salesperson(clean_df)
        region_df = stats_by_region(clean_df)
        total = calculate_total(clean_df)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        export_report(clean_df, salesperson_df, region_df, total, str(output_path))
    except ValueError as exc:
        print(f"错误：{exc}")
        return 1
    except Exception as exc:
        print("程序运行异常：" + str(exc))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
