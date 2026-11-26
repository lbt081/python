# FastAPI 简易记账接口

基于 FastAPI + SQLAlchemy + SQLite 的记账服务，支持新增流水、条件查询、分页和区间收支汇总。

## 1. 功能简介

| 功能 | 说明 |
|---|---|
| 新增流水 | 记录金额、类型（收入/支出）、分类、日期 |
| 条件查询 | 按类型精确筛选、按分类模糊匹配、按日期闭区间筛选 |
| 分页 | 支持 `page`、`page_size`，按日期倒序返回 |
| 区间汇总 | 统计指定日期范围内的收入合计、支出合计与结余 |
| 参数校验 | 金额、类型、日期、分页参数全部由 Pydantic 校验 |
| 统一错误 | 所有参数错误和 HTTP 异常返回 `{"detail": "错误描述"}` |
| 自动建表 | 应用启动时自动创建 SQLite 表 |

**本期范围**：单用户使用，不含登录、多用户隔离、修改/删除流水、分类管理。

## 2. 目录结构

```text
exam2_fastapi_account/
├── main.py          # FastAPI 应用、路由、全局异常处理
├── database.py      # 数据库连接、ORM 模型、Pydantic 模型
├── account.db       # 运行后自动生成的 SQLite 文件
└── README.md        # 本文档
```

## 3. 环境依赖

| 项目 | 要求 |
|---|---|
| Python | 3.10 及以上 |
| FastAPI | 0.115 及以上 |
| Uvicorn | 0.30 及以上 |
| Pydantic | 2.7 及以上 |
| SQLAlchemy | 2.0（本项目在 2.0.58 下验证通过） |
| 测试（可选） | pytest、httpx |

安装：

```bash
pip install "fastapi>=0.115" "uvicorn[standard]>=0.30" "pydantic>=2.7" "sqlalchemy>=2.0,<2.1"
pip install pytest httpx
```

## 4. 启动方式

在 `exam2_fastapi_account` 目录下执行：

```bash
uvicorn main:app --reload --port 8000
```

启动后：

- 服务地址：http://127.0.0.1:8000
- 交互文档：http://127.0.0.1:8000/docs
- OpenAPI JSON：http://127.0.0.1:8000/openapi.json

首次启动会自动在 `database.py` 同级目录创建 `account.db`，无需手动建库。删除该文件即可重置数据。

## 5. 接口清单

### 5.1 GET / —— 服务状态

返回服务名称、运行状态、版本和文档地址。

**响应示例：200 OK**

```json
{
  "service": "简易记账 API",
  "status": "running",
  "version": "1.0.0",
  "docs": "/docs"
}
```

### 5.2 POST /records —— 新增流水

**请求体**

| 字段 | 类型 | 必填 | 规则 |
|---|---|---|---|
| amount | number | 是 | 大于 0，最多 2 位小数 |
| type | string | 是 | 仅允许 `收入` 或 `支出` |
| category | string | 是 | 1～50 个字符，首尾空格会被去除 |
| date | string | 是 | `YYYY-MM-DD`，必须是真实日期 |

**请求示例**

```json
{
  "amount": 128.50,
  "type": "支出",
  "category": "餐饮",
  "date": "2026-11-20"
}
```

**响应示例：201 Created**

```json
{
  "id": 1,
  "amount": 128.5,
  "type": "支出",
  "category": "餐饮",
  "date": "2026-11-20",
  "created_at": "2026-11-21T20:10:08.423683"
}
```

**校验失败：400 Bad Request**

```json
{
  "detail": "amount: Input should be greater than 0；type: Input should be '收入' or '支出'"
}
```

### 5.3 GET /records —— 条件查询与分页

**查询参数**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| type | string | 否 | 无 | `收入` 或 `支出`，精确匹配 |
| category | string | 否 | 无 | 分类，模糊匹配 |
| start_date | string | 否 | 无 | 起始日期（含），`YYYY-MM-DD` |
| end_date | string | 否 | 无 | 结束日期（含），`YYYY-MM-DD` |
| page | integer | 否 | 1 | 页码，必须 ≥ 1 |
| page_size | integer | 否 | 10 | 每页条数，1～100 |

**请求示例**

```text
GET /records?type=支出&category=餐&start_date=2026-11-01&end_date=2026-11-30&page=1&page_size=10
```

**响应示例：200 OK**

```json
{
  "total": 1,
  "page": 1,
  "page_size": 10,
  "items": [
    {
      "id": 1,
      "amount": 128.5,
      "type": "支出",
      "category": "餐饮",
      "date": "2026-11-20",
      "created_at": "2026-11-21T20:10:08.423683"
    }
  ]
}
```

**规则**

- 多个条件之间是“与”关系；
- 日期区间为闭区间；
- 按 `date` 降序，同一天按 `id` 降序；
- 页码超出范围时 `items` 为空数组，`total` 仍为真实总数；
- `page < 1`、`page_size` 超出 1～100、日期格式错误、`start_date > end_date` 均返回 400。

### 5.4 GET /summary —— 区间收支汇总

**查询参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| start_date | string | 是 | 起始日期（含），`YYYY-MM-DD` |
| end_date | string | 是 | 结束日期（含），`YYYY-MM-DD` |

**请求示例**

```text
GET /summary?start_date=2026-11-01&end_date=2026-11-30
```

**响应示例：200 OK**

```json
{
  "income_total": 5000.0,
  "expense_total": 128.5,
  "balance": 4871.5
}
```

**规则**

- `income_total` 为区间内所有“收入”的金额之和；
- `expense_total` 为区间内所有“支出”的金额之和；
- `balance = income_total - expense_total`；
- 区间内无数据时三项均为 `0.0`；
- 金额保留 2 位小数；
- 缺少日期、日期格式错误或 `start_date > end_date` 返回 400。

### 5.5 统一错误格式

所有参数错误和 HTTP 异常均返回：

```json
{
  "detail": "错误描述"
}
```

| 状态码 | 场景 |
|---|---|
| 400 | 参数类型、格式、范围错误；日期区间非法 |
| 404 | 请求的资源不存在 |
| 405 | 请求方法不允许 |
| 500 | 服务器内部错误 |

## 6. 测试方法

### 6.1 使用 Swagger 手工测试

1. 启动服务，打开 http://127.0.0.1:8000/docs
2. 展开 `POST /records`，点击 Try it out，填入请求体后 Execute
3. 用 `GET /records` 和 `GET /summary` 验证查询与汇总

### 6.2 使用 PowerShell 调用

```powershell
# 新增一条支出
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/records' -Method Post `
  -ContentType 'application/json' `
  -Body '{"amount":128.5,"type":"支出","category":"餐饮","date":"2026-11-20"}'

# 查询支出记录
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/records?type=%E6%94%AF%E5%87%BA&page=1&page_size=10'

# 汇总
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/summary?start_date=2026-11-01&end_date=2026-11-30'
```

### 6.3 使用 pytest + TestClient

```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_create_record():
    response = client.post(
        "/records",
        json={"amount": 128.5, "type": "支出", "category": "餐饮", "date": "2026-11-20"},
    )
    assert response.status_code == 201
    assert response.json()["amount"] == 128.5


def test_invalid_amount_returns_400():
    response = client.post(
        "/records",
        json={"amount": 0, "type": "支出", "category": "餐饮", "date": "2026-11-20"},
    )
    assert response.status_code == 400
    assert "detail" in response.json()


def test_summary():
    response = client.get(
        "/summary", params={"start_date": "2026-11-01", "end_date": "2026-11-30"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["balance"] == data["income_total"] - data["expense_total"]
```

运行：

```bash
pytest -q
```

### 6.4 建议覆盖的测试场景

| 类别 | 场景 |
|---|---|
| 新增 | 合法收入、合法支出；金额为 0/负数/三位小数；类型非法；日期非法；分类为空或超长 |
| 查询 | 无条件、按类型、按分类模糊、按日期区间、组合条件；日期边界包含 |
| 分页 | 默认分页、第二页、超范围页码；`page=0`、`page_size=101` |
| 汇总 | 有收入有支出、只有一种类型、区间无数据、`start_date > end_date` |
| 异常 | 404 路径、405 方法、500 兜底格式 |

## 7. 说明与限制

1. 金额使用 `Float` 存储，接口展示保留 2 位小数；对金额精度要求更高的场景建议改为整数分存储。
2. SQLite 已启用 WAL 与 5 秒忙等待，适合单机和小规模并发；多进程高并发写入需额外评估。
3. 本期不做用户认证，所有请求共享同一份数据。
4. 重复提交同一请求会产生两条流水，接口不做幂等处理。
