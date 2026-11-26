"""
FastAPI 简易记账 API

启动命令：
    uvicorn main:app --reload --port 8000

接口：
    GET  /            服务状态
    POST /records     新增流水
    GET  /records     条件查询与分页
    GET  /summary     区间收支汇总
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date as date_type

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import case, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from database import (
    PageResult,
    Record,
    RecordCreate,
    RecordResponse,
    RecordType,
    SummaryResult,
    get_db,
    init_db,
)

logger = logging.getLogger("account_api")


# ============================================================
# 一、应用初始化
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时自动建表。"""
    init_db()
    yield


app = FastAPI(
    title="简易记账 API",
    description="基于 FastAPI + SQLite 的记账接口，支持新增、查询、汇总。",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================
# 二、全局异常处理
# ============================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """把参数校验错误统一转换为 400，并返回 {"detail": "..."}。"""
    messages: list[str] = []
    for error in exc.errors():
        location = ".".join(
            str(part) for part in error["loc"] if part not in ("body", "query", "path")
        )
        messages.append(f"{location or '参数'}: {error['msg']}")

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "；".join(messages) or "请求参数校验失败"},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """把 HTTPException 统一转换为 {"detail": "..."}。"""
    detail = exc.detail

    # 兼容 detail 为字典的写法，只提取可读信息
    if isinstance(detail, dict):
        detail = detail.get("message") or detail.get("error") or str(detail)

    # 404 / 405 使用中文提示
    if exc.status_code == status.HTTP_404_NOT_FOUND and detail == "Not Found":
        detail = "请求的资源不存在"
    elif exc.status_code == status.HTTP_405_METHOD_NOT_ALLOWED and detail == "Method Not Allowed":
        detail = "请求方法不允许"

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(detail)},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底处理未预期异常，避免向客户端暴露堆栈。"""
    logger.exception("未处理异常：%s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "服务器内部错误"},
    )


# ============================================================
# 三、服务状态
# ============================================================

@app.get("/", tags=["health"])
def root() -> dict:
    """返回服务运行状态说明。"""
    return {
        "service": "简易记账 API",
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs",
    }


# ============================================================
# 四、流水接口
# ============================================================

@app.post(
    "/records",
    response_model=RecordResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["records"],
)
def create_record(
    payload: RecordCreate,
    db: Session = Depends(get_db),
) -> RecordResponse:
    """新增一条流水，成功返回 201 和完整记录。"""
    record = Record(
        amount=payload.amount,
        type=payload.type.value,
        category=payload.category,
        date=payload.date,
    )

    try:
        db.add(record)
        db.commit()
        db.refresh(record)
    except SQLAlchemyError:
        db.rollback()
        raise

    return record


@app.get(
    "/records",
    response_model=PageResult,
    status_code=status.HTTP_200_OK,
    tags=["records"],
)
def list_records(
    record_type: RecordType | None = Query(
        default=None,
        alias="type",
        description="类型，精确匹配：收入 / 支出",
    ),
    category: str | None = Query(
        default=None,
        description="分类，模糊匹配",
    ),
    start_date: date_type | None = Query(
        default=None,
        description="起始日期（含），格式 YYYY-MM-DD",
    ),
    end_date: date_type | None = Query(
        default=None,
        description="结束日期（含），格式 YYYY-MM-DD",
    ),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页条数，1～100"),
    db: Session = Depends(get_db),
) -> PageResult:
    """按类型、分类、日期区间筛选流水，返回分页结果，按日期倒序。"""
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date 不能晚于 end_date",
        )

    stmt = select(Record)

    if record_type is not None:
        stmt = stmt.where(Record.type == record_type.value)

    if category is not None:
        keyword = category.strip()
        if keyword:
            stmt = stmt.where(Record.category.like(f"%{keyword}%"))

    if start_date is not None:
        stmt = stmt.where(Record.date >= start_date)

    if end_date is not None:
        stmt = stmt.where(Record.date <= end_date)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    stmt = (
        stmt.order_by(Record.date.desc(), Record.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    records = db.scalars(stmt).all()

    return PageResult(
        total=total,
        page=page,
        page_size=page_size,
        items=[RecordResponse.model_validate(record) for record in records],
    )


@app.get(
    "/summary",
    response_model=SummaryResult,
    status_code=status.HTTP_200_OK,
    tags=["summary"],
)
def get_summary(
    start_date: date_type = Query(
        ...,
        description="起始日期（含），格式 YYYY-MM-DD",
    ),
    end_date: date_type = Query(
        ...,
        description="结束日期（含），格式 YYYY-MM-DD",
    ),
    db: Session = Depends(get_db),
) -> SummaryResult:
    """统计指定日期闭区间内的收入合计、支出合计与结余。"""
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date 不能晚于 end_date",
        )

    stmt = (
        select(
            func.coalesce(
                func.sum(case((Record.type == "收入", Record.amount), else_=0.0)),
                0.0,
            ),
            func.coalesce(
                func.sum(case((Record.type == "支出", Record.amount), else_=0.0)),
                0.0,
            ),
        )
        .where(Record.date >= start_date)
        .where(Record.date <= end_date)
    )

    income_raw, expense_raw = db.execute(stmt).one()

    income_total = round(float(income_raw or 0), 2)
    expense_total = round(float(expense_raw or 0), 2)
    balance = round(income_total - expense_total, 2)

    return SummaryResult(
        income_total=income_total,
        expense_total=expense_total,
        balance=balance,
    )
