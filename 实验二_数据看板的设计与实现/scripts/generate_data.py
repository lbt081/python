# -*- coding: utf-8 -*-
"""生成电商销售模拟原始数据，并故意注入少量脏数据，供预处理环节演示。

运行：
    python scripts/generate_data.py

输出：
    data/raw_sales_data.csv    原始数据（含空值、重复、异常值、格式不统一）
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_FILE = BASE_DIR / "data" / "raw_sales_data.csv"

RNG = np.random.default_rng(42)

REGION_PROVINCE = {
    "华东": ["上海", "江苏", "浙江", "安徽", "福建", "江西", "山东"],
    "华南": ["广东", "广西", "海南"],
    "华北": ["北京", "天津", "河北", "山西", "内蒙古"],
    "华中": ["河南", "湖北", "湖南"],
    "西南": ["重庆", "四川", "贵州", "云南", "西藏"],
    "西北": ["陕西", "甘肃", "青海", "宁夏", "新疆"],
    "东北": ["辽宁", "吉林", "黑龙江"],
}

REGION_WEIGHTS = [0.32, 0.20, 0.18, 0.12, 0.09, 0.05, 0.04]

CATEGORY_CONFIG = {
    "数码家电": {"price": (599, 2999), "margin": 0.18, "refund": 0.035, "weight": 0.12},
    "服饰鞋包": {"price": (129, 899), "margin": 0.36, "refund": 0.060, "weight": 0.26},
    "食品生鲜": {"price": (29, 299), "margin": 0.22, "refund": 0.045, "weight": 0.20},
    "美妆个护": {"price": (89, 699), "margin": 0.40, "refund": 0.030, "weight": 0.16},
    "家居日用": {"price": (59, 499), "margin": 0.28, "refund": 0.025, "weight": 0.14},
    "运动户外": {"price": (159, 1599), "margin": 0.30, "refund": 0.032, "weight": 0.12},
}

CHANNELS = ["APP", "小程序", "PC官网", "线下门店"]
CHANNEL_WEIGHTS = [0.50, 0.25, 0.15, 0.10]

MONTH_FACTOR = {
    1: 0.95, 2: 0.78, 3: 1.00, 4: 0.96, 5: 1.08, 6: 1.35,
    7: 0.90, 8: 0.94, 9: 1.00, 10: 1.12, 11: 1.55, 12: 1.20,
}
YEAR_FACTOR = {2024: 0.85, 2025: 1.00}


def generate_orders() -> pd.DataFrame:
    categories = list(CATEGORY_CONFIG)
    category_weights = [CATEGORY_CONFIG[c]["weight"] for c in categories]
    regions = list(REGION_PROVINCE)
    records = []
    order_seq = 0

    for year in (2024, 2025):
        current = pd.Timestamp(f"{year}-01-01")
        end = pd.Timestamp(f"{year}-12-31")
        while current <= end:
            month_factor = MONTH_FACTOR[current.month]
            weekend_factor = 1.15 if current.weekday() >= 5 else 1.0
            daily_count = int(
                max(1, RNG.poisson(8) * month_factor * weekend_factor * YEAR_FACTOR[year])
            )

            for _ in range(daily_count):
                order_seq += 1
                category = RNG.choice(categories, p=category_weights)
                cfg = CATEGORY_CONFIG[category]
                region = RNG.choice(regions, p=REGION_WEIGHTS)
                province = RNG.choice(REGION_PROVINCE[region])
                channel = RNG.choice(CHANNELS, p=CHANNEL_WEIGHTS)

                quantity = int(RNG.choice([1, 1, 1, 2, 2, 3, 4, 5]))
                low, high = cfg["price"]
                unit_price = round(float(RNG.uniform(low, high)), 2)
                discount = round(float(RNG.uniform(0.82, 1.0)), 2)
                sales = round(quantity * unit_price * discount, 2)

                margin = cfg["margin"] + float(RNG.normal(0, 0.035))
                margin = min(0.55, max(0.05, margin))
                cost = round(sales * (1 - margin), 2)
                profit = round(sales - cost, 2)

                rating = float(np.clip(RNG.normal(4.45, 0.32), 3.0, 5.0))
                is_refund = int(RNG.random() < cfg["refund"])
                refund_amount = sales if is_refund else 0.0

                records.append(
                    {
                        "order_id": f"SO{year}{order_seq:06d}",
                        "order_date": current.strftime("%Y-%m-%d"),
                        "region": region,
                        "province": province,
                        "category": category,
                        "channel": channel,
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "discount": discount,
                        "sales_amount": sales,
                        "cost": cost,
                        "profit": profit,
                        "rating": round(rating, 2),
                        "is_new_customer": int(RNG.random() < 0.32),
                        "is_refund": is_refund,
                        "refund_amount": refund_amount,
                    }
                )
            current += pd.Timedelta(days=1)

    return pd.DataFrame(records)


def inject_quality_issues(df: pd.DataFrame) -> pd.DataFrame:
    """注入空值、重复、负销售额、格式不统一和极端值，模拟真实脏数据。"""
    dirty = df.copy()

    # 格式不统一：渠道前后空格、大小写混用
    dirty.loc[dirty.sample(18, random_state=1).index, "channel"] = " APP "
    dirty.loc[dirty.sample(10, random_state=2).index, "channel"] = "app"
    dirty.loc[dirty.sample(8, random_state=3).index, "channel"] = "小程序 "

    # 关键字段空值
    dirty.loc[dirty.sample(22, random_state=4).index, "region"] = np.nan
    dirty.loc[dirty.sample(14, random_state=5).index, "channel"] = np.nan
    dirty.loc[dirty.sample(10, random_state=6).index, "category"] = np.nan
    dirty.loc[dirty.sample(15, random_state=7).index, "quantity"] = np.nan
    dirty.loc[dirty.sample(12, random_state=8).index, "unit_price"] = np.nan

    # 异常值：负销售额、超大数量、评分越界
    dirty.loc[dirty.sample(9, random_state=9).index, "sales_amount"] = -999.0
    dirty.loc[dirty.sample(6, random_state=10).index, "quantity"] = 999
    dirty.loc[dirty.sample(7, random_state=11).index, "rating"] = 6.8

    # 重复记录
    duplicates = dirty.sample(12, random_state=12)
    dirty = pd.concat([dirty, duplicates], ignore_index=True)

    return dirty.sample(frac=1, random_state=13).reset_index(drop=True)


def main() -> None:
    clean = generate_orders()
    raw = inject_quality_issues(clean)
    RAW_FILE.parent.mkdir(parents=True, exist_ok=True)
    raw.to_csv(RAW_FILE, index=False, encoding="utf-8-sig")
    print(f"原始数据已生成：{RAW_FILE}")
    print(f"行数：{len(raw)}，列数：{len(raw.columns)}")
    print(f"日期范围：{raw['order_date'].min()} 至 {raw['order_date'].max()}")


if __name__ == "__main__":
    main()
