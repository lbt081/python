"""
记账 API 接口测试

运行命令：
    python -m pytest test_api.py -v

说明：
    1. 使用 FastAPI TestClient 直接调用接口，无需启动 uvicorn；
    2. 必须在导入 main / database 之前设置 DATABASE_URL，
       使应用连接到内存 SQLite（sqlite:///:memory:），不会创建或修改正式库 account.db；
    3. database.py 对内存库使用 StaticPool，保证 TestClient 的多线程共享同一个内存数据库。
"""

from __future__ import annotations

import os

# 关键：必须先于 main / database 的导入执行
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from database import Record, SessionLocal, engine
from main import app

# 安全阀：一旦配置失效，立即失败，避免误写正式数据库
assert str(engine.url) == "sqlite:///:memory:", "测试必须使用内存数据库"


# ============================================================
# 测试夹具与辅助函数
# ============================================================

def _clear_records() -> None:
    """清空内存库中的流水，避免用例之间相互影响。"""
    db = SessionLocal()
    try:
        db.execute(delete(Record))
        db.commit()
    finally:
        db.close()


@pytest.fixture()
def client():
    """每个用例使用独立的 TestClient，并保证内存库从空表开始。"""
    _clear_records()
    with TestClient(app) as test_client:
        yield test_client


def post_record(
    client: TestClient,
    amount: float,
    record_type: str = "收入",
    category: str = "工资",
    record_date: str = "2026-11-01",
):
    """新增一条流水，返回响应对象。"""
    return client.post(
        "/records",
        json={
            "amount": amount,
            "type": record_type,
            "category": category,
            "date": record_date,
        },
    )


# ============================================================
# 一、正常用例
# ============================================================

def test_create_income_and_query_summary(client: TestClient) -> None:
    """新增收入 5000 → 201；查询能返回该数据；汇总数值正确。"""
    response = post_record(client, amount=5000, category="工资", record_date="2026-11-01")
    assert response.status_code == 201

    created = response.json()
    assert created["id"] > 0
    assert created["amount"] == 5000
    assert created["type"] == "收入"
    assert created["category"] == "工资"
    assert created["date"] == "2026-11-01"
    assert created["created_at"]

    # 查询接口能返回该数据
    listed = client.get("/records", params={"type": "收入", "page": 1, "page_size": 10})
    assert listed.status_code == 200

    page = listed.json()
    assert page["total"] == 1
    assert page["page"] == 1
    assert page["page_size"] == 10
    assert len(page["items"]) == 1
    assert page["items"][0]["id"] == created["id"]
    assert page["items"][0]["amount"] == 5000

    # 汇总接口数值正确
    summary = client.get(
        "/summary",
        params={"start_date": "2026-11-01", "end_date": "2026-11-30"},
    )
    assert summary.status_code == 200
    assert summary.json() == {
        "income_total": 5000.0,
        "expense_total": 0.0,
        "balance": 5000.0,
    }


# ============================================================
# 二、异常用例
# ============================================================

def test_create_record_with_negative_amount(client: TestClient) -> None:
    """金额为负数 → 400。"""
    response = post_record(client, amount=-100, category="工资")
    assert response.status_code == 400

    body = response.json()
    assert "detail" in body
    assert "amount" in body["detail"]

    # 确认失败请求没有写入数据
    assert client.get("/records").json()["total"] == 0


def test_create_record_with_invalid_type(client: TestClient) -> None:
    """类型为“转账” → 400。"""
    response = post_record(client, amount=100, record_type="转账", category="其他")
    assert response.status_code == 400

    body = response.json()
    assert "detail" in body
    assert "type" in body["detail"]

    assert client.get("/records").json()["total"] == 0


def test_create_record_with_invalid_date(client: TestClient) -> None:
    """日期格式错误（2026-02-30 不存在）→ 400。"""
    response = post_record(client, amount=100, record_date="2026-02-30")
    assert response.status_code == 400

    body = response.json()
    assert "detail" in body
    assert "date" in body["detail"]

    assert client.get("/records").json()["total"] == 0


# ============================================================
# 三、分页测试
# ============================================================

def test_pagination_second_page_returns_five_items(client: TestClient) -> None:
    """批量插入 15 条，第 2 页（每页 10 条）返回 5 条。"""
    for day in range(1, 16):
        response = post_record(
            client,
            amount=float(day * 10),
            category=f"测试分类{day:02d}",
            record_date=f"2026-11-{day:02d}",
        )
        assert response.status_code == 201

    response = client.get("/records", params={"page": 2, "page_size": 10})
    assert response.status_code == 200

    page = response.json()
    assert page["total"] == 15
    assert page["page"] == 2
    assert page["page_size"] == 10
    assert len(page["items"]) == 5

    # 接口按日期倒序，第 2 页应为最早的 5 条：11-05 ~ 11-01
    assert [item["date"] for item in page["items"]] == [
        "2026-11-05",
        "2026-11-04",
        "2026-11-03",
        "2026-11-02",
        "2026-11-01",
    ]


# ============================================================
# 四、汇总测试
# ============================================================

def test_summary_with_income_and_expense(client: TestClient) -> None:
    """3 条收入、2 条支出 → 收入 3500、支出 500、结余 3000。"""
    for amount, record_date in ((1000, "2026-11-01"), (2000, "2026-11-02"), (500, "2026-11-03")):
        assert post_record(client, amount=amount, record_type="收入", record_date=record_date).status_code == 201

    for amount, record_date in ((300, "2026-11-04"), (200, "2026-11-05")):
        assert post_record(
            client,
            amount=amount,
            record_type="支出",
            category="餐饮",
            record_date=record_date,
        ).status_code == 201

    response = client.get(
        "/summary",
        params={"start_date": "2026-11-01", "end_date": "2026-11-30"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "income_total": 3500.0,
        "expense_total": 500.0,
        "balance": 3000.0,
    }
