# -*- coding: utf-8 -*-
"""清洗电商销售原始数据，生成看板可直接使用的分析数据。

处理内容：
    1. 去除重复订单；
    2. 统一渠道写法（空格、大小写）；
    3. 删除关键字段缺失的记录；
    4. 修正负销售额、超大数量、评分越界等异常值；
    5. 重新计算销售额、利润、退款金额；
    6. 派生年、月、季度、星期等时间维度。

运行：
    python scripts/preprocess.py

输出：
    data/sales_data.csv          清洗后的分析数据
    data/cleaning_summary.txt    清洗结果摘要
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_FILE = BASE_DIR / "data" / "raw_sales_data.csv"
CLEAN_FILE = BASE_DIR / "data" / "sales_data.csv"
SUMMARY_FILE = BASE_DIR / "data" / "cleaning_summary.txt"

CATEGORY_MARGIN = {
    "数码家电": 0.18,
    "服饰鞋包": 0.36,
    "食品生鲜": 0.22,
    "美妆个护": 0.40,
    "家居日用": 0.28,
    "运动户外": 0.30,
}


def normalize_channel(value: object) -> object:
    """把 ' APP '、'app'、'小程序 ' 等写法统一成标准渠道名。"""
    if pd.isna(value):
        return np.nan
    text = str(value).strip()
    upper = text.upper()
    if "APP" in upper:
        return "APP"
    if "小程序" in text:
        return "小程序"
    if "PC" in upper:
        return "PC官网"
    if "线下" in text:
        return "线下门店"
    return text


def main() -> None:
    raw = pd.read_csv(RAW_FILE, encoding="utf-8-sig")
    before = len(raw)

    df = raw.copy()
    text_columns = ["region", "province", "category", "channel"]
    for column in text_columns:
        df[column] = df[column].astype("string").str.strip()
    df["channel"] = df["channel"].map(normalize_channel)

    duplicated = int(df.duplicated(subset="order_id").sum())
    df = df.drop_duplicates(subset="order_id", keep="first")

    critical = ["order_date", "region", "province", "category", "channel", "quantity", "unit_price"]
    missing_rows = int(df[critical].isna().any(axis=1).sum())
    df = df.dropna(subset=critical)

    numeric_columns = [
        "quantity", "unit_price", "discount", "sales_amount",
        "cost", "profit", "rating", "is_new_customer", "is_refund", "refund_amount",
    ]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df["discount"] = df["discount"].fillna(1.0).clip(0.5, 1.0)
    quantity_outliers = int(((df["quantity"] < 1) | (df["quantity"] > 8)).sum())
    df = df[(df["quantity"] >= 1) & (df["quantity"] <= 8)]
    df = df[df["unit_price"] > 0]

    # 销售额以数量、单价、折扣为准重新计算，自动修复负数和不一致
    quantity = df["quantity"].astype(int)
    df["sales_amount"] = (quantity * df["unit_price"] * df["discount"]).round(2)

    # 成本缺失时按品类平均毛利率估算
    category_margin = df["category"].map(CATEGORY_MARGIN).fillna(0.28)
    fallback_cost = df["sales_amount"] * (1 - category_margin)
    df["cost"] = df["cost"].where(df["cost"].notna() & (df["cost"] > 0), fallback_cost).round(2)
    df["cost"] = df["cost"].clip(lower=0, upper=df["sales_amount"])
    df["profit"] = (df["sales_amount"] - df["cost"]).round(2)

    rating_outliers = int(((df["rating"] < 3) | (df["rating"] > 5)).sum())
    df["rating"] = df["rating"].fillna(4.5).clip(3.0, 5.0).round(2)
    df["is_refund"] = df["is_refund"].fillna(0).astype(int).clip(0, 1)
    df["refund_amount"] = np.where(df["is_refund"] == 1, df["sales_amount"], 0.0).round(2)
    df["is_new_customer"] = df["is_new_customer"].fillna(0).astype(int).clip(0, 1)

    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df = df.dropna(subset=["order_date"])
    df["year"] = df["order_date"].dt.year
    df["month"] = df["order_date"].dt.month
    df["quarter"] = df["order_date"].dt.quarter
    df["month_label"] = df["order_date"].dt.strftime("%Y-%m")
    df["weekday"] = df["order_date"].dt.dayofweek + 1
    df["week"] = df["order_date"].dt.isocalendar().week.astype(int)

    df = df.sort_values("order_date").reset_index(drop=True)
    df.to_csv(CLEAN_FILE, index=False, encoding="utf-8-sig")

    total_sales = df["sales_amount"].sum()
    total_profit = df["profit"].sum()
    summary = f"""电商销售数据清洗摘要
========================================
原始记录数：{before}
重复订单数：{duplicated}
关键字段缺失：{missing_rows}
数量异常：{quantity_outliers}
评分越界：{rating_outliers}
清洗后记录数：{len(df)}
日期范围：{df['order_date'].min().date()} 至 {df['order_date'].max().date()}
总销售额：{total_sales:,.2f} 元
总利润：{total_profit:,.2f} 元
整体利润率：{total_profit / total_sales:.2%}
整体退款率：{df['is_refund'].mean():.2%}
平均客单价：{total_sales / len(df):,.2f} 元
"""
    SUMMARY_FILE.write_text(summary, encoding="utf-8")
    print(summary)
    print(f"清洗后数据已保存：{CLEAN_FILE}")


if __name__ == "__main__":
    main()
