"""
FastAPI 记账系统数据层

包含：
    1. SQLite 数据库连接与会话管理；
    2. SQLAlchemy ORM 模型 Record；
    3. Pydantic 请求 / 响应模型。

数据库文件默认位于当前目录 account.db，导入本模块时自动建表。
"""

from __future__ import annotations

import os
from datetime import date as date_type
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Generator

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    create_engine,
    event,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool


# ============================================================
# 一、数据库连接
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "account.db"

# 默认使用正式数据库文件；测试可通过 DATABASE_URL 指向内存库
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

# check_same_thread=False 允许 FastAPI 在不同线程中使用同一连接池
engine_kwargs = {
    "connect_args": {"check_same_thread": False},
    "future": True,
}

# 内存 SQLite 必须使用 StaticPool，保证多个会话共享同一个内存数据库
if DATABASE_URL in ("sqlite://", "sqlite:///:memory:"):
    engine_kwargs["poolclass"] = StaticPool

engine = create_engine(DATABASE_URL, **engine_kwargs)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    """每次建立连接时启用 WAL 与忙等待，降低并发写入时的锁冲突。"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy 2.x 声明式基类。"""


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每个请求创建一个 Session，请求结束后自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# 二、ORM 模型
# ============================================================

class Record(Base):
    """记账流水表。"""

    __tablename__ = "records"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_records_amount_positive"),
        CheckConstraint("type IN ('收入', '支出')", name="ck_records_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )

    def __repr__(self) -> str:
        return (
            f"Record(id={self.id}, amount={self.amount}, type={self.type!r}, "
            f"category={self.category!r}, date={self.date})"
        )


# ============================================================
# 三、Pydantic 模型
# ============================================================

class RecordType(str, Enum):
    """收支类型枚举。"""

    INCOME = "收入"
    EXPENSE = "支出"


class RecordCreate(BaseModel):
    """POST /records 请求体。"""

    amount: float = Field(gt=0, allow_inf_nan=False, description="金额，必须大于 0")
    type: RecordType = Field(description="类型：收入 / 支出")
    category: str = Field(min_length=1, max_length=50, description="分类")
    date: date_type = Field(description="业务日期，格式 YYYY-MM-DD")

    model_config = ConfigDict(extra="forbid")

    @field_validator("category")
    @classmethod
    def strip_category(cls, value: str) -> str:
        """去除分类首尾空格，并拒绝纯空白。"""
        value = value.strip()
        if not value:
            raise ValueError("分类不能为空")
        return value


class RecordResponse(BaseModel):
    """单条流水返回体。"""

    id: int
    amount: float
    type: RecordType
    category: str
    date: date_type
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PageResult(BaseModel):
    """分页返回结构。"""

    total: int
    page: int
    page_size: int
    items: list[RecordResponse]


class SummaryResult(BaseModel):
    """区间汇总返回体。"""

    income_total: float
    expense_total: float
    balance: float


# ============================================================
# 四、初始化
# ============================================================

def init_db() -> None:
    """创建所有表；重复调用不会删除已有数据。"""
    Base.metadata.create_all(bind=engine)


# 导入模块即自动建表，满足“启动自动建表”要求
init_db()


if __name__ == "__main__":
    print(f"数据库已初始化：{DB_PATH}")
