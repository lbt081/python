# 需求澄清清单：FastAPI 简易记账接口

| 项目 | 内容 |
|---|---|
| 文档编号 | REQ-API-001 |
| 版本 | V1.0 |
| 日期 | 2026-11-21 |
| 编写人 | 刘宝廷 |
| 状态 | 待确认（确认后作为开发与验收依据） |

---

## 1. 核心目标

1. 提供一套基于 HTTP 的记账接口，支持新增流水、条件查询和区间汇总。
2. 使用 SQLite 单文件存储，不依赖额外数据库服务，开箱即用。
3. 所有输入经过严格校验，非法参数返回 4xx 和结构化错误信息。
4. 在并发写入场景下保证数据不丢失、不重复、金额一致。
5. 自动生成 OpenAPI 文档，便于联调和验收。

**非目标（本期不做）**：用户注册登录与多用户隔离、修改/删除流水、预算与图表、分类管理、导入导出、多币种、定时任务。

**默认前提**：单用户使用，人民币记账，金额保留 2 位小数；如后续需要多用户，需新增 `user_id` 并调整权限模型。

---

## 2. 存储方案

### 2.1 数据库选型

| 项目 | 方案 |
|---|---|
| 数据库 | SQLite 3（Python 标准库自带） |
| 文件位置 | 默认 `./data/account.db`，可通过环境变量 `DATABASE_URL` 覆盖 |
| 访问方式 | SQLAlchemy 2.x（同步 Session） |
| 建表方式 | 应用启动时自动 `create_all`，本期不做迁移 |
| 字符编码 | UTF-8 |
| 时区 | `record_date` 为本地日历日期；`created_at` 存 UTC |

### 2.2 表结构：records

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | INTEGER | 主键，自增 | 服务端生成，客户端不得传入 |
| amount_cents | INTEGER | NOT NULL，CHECK > 0 | 金额按“分”存储，避免浮点误差 |
| type | TEXT | NOT NULL，CHECK IN ('收入','支出') | 收支类型 |
| category | TEXT | NOT NULL，长度 1～50 | 分类名称，去除首尾空格后存储 |
| record_date | TEXT | NOT NULL，格式 YYYY-MM-DD | 业务日期 |
| created_at | TEXT | NOT NULL，默认当前 UTC 时间 | 创建时间，ISO 8601 |

**金额存储说明**：接口层 `amount` 为元、最多 2 位小数；写入时转换为整数分（`round(amount × 100)`），读取时除以 100 返回。禁止用 REAL 存储金额。

**索引**：

- `idx_records_type_date (type, record_date)`
- `idx_records_category (category)`
- `idx_records_date (record_date)`

### 2.3 并发写入与一致性保证

SQLite 同一时刻只允许一个写事务，方案如下：

1. 启用 WAL：`PRAGMA journal_mode=WAL;`，读写互不阻塞。
2. 设置忙等待：`PRAGMA busy_timeout=5000;`，写锁冲突时最多等待 5 秒。
3. 每个 POST 请求使用独立 Session，写操作放在单个事务中：校验 → 插入 → commit；异常统一 rollback。
4. 写事务使用 `BEGIN IMMEDIATE`，提前获取写锁，避免“读升级为写”导致的死锁。
5. 捕获 `SQLITE_BUSY` 后重试 3 次（间隔 100ms / 300ms / 700ms）；仍失败返回 503 `DB_BUSY`。
6. 数据库层增加 CHECK 约束，作为应用校验之外的最后防线。
7. 本期不提供修改接口，不存在丢失更新问题；POST 为原子插入，不会产生半条记录。
8. 课程演示建议 `uvicorn --workers 1`；多 worker 时仍由 SQLite 串行化写入，依靠 busy_timeout 与重试保证成功。
9. 汇总查询在单条 SQL 内完成，读取的是同一事务快照，收入、支出、结余三者口径一致。

**已知限制**：不提供幂等键，客户端超时重试可能产生重复流水；如需严格幂等，后续增加 `Idempotency-Key`。

---

## 3. 接口详情

通用约定：

- 基础路径：`/`，所有请求与响应均为 `application/json; charset=utf-8`。
- 金额单位：元，最多 2 位小数。
- 日期格式：`YYYY-MM-DD`。
- 成功响应直接返回业务数据；错误响应使用统一结构（见第 5 节）。
- 交互式文档：`/docs`、`/openapi.json`。

### 3.1 POST /records —— 新增流水

**请求体**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| amount | number | 是 | 金额，> 0，最多 2 位小数 |
| type | string | 是 | 仅允许 `收入` 或 `支出` |
| category | string | 是 | 1～50 个字符，去除首尾空格后不能为空 |
| date | string | 是 | `YYYY-MM-DD`，必须是真实存在的日期 |

请求示例：

```json
{
  "amount": 128.50,
  "type": "支出",
  "category": "餐饮",
  "date": "2026-11-20"
}
```

**成功响应：201 Created**

```json
{
  "id": 1,
  "amount": 128.50,
  "type": "支出",
  "category": "餐饮",
  "date": "2026-11-20",
  "created_at": "2026-11-20T12:30:45Z"
}
```

**业务规则**：

- 服务端生成 `id` 与 `created_at`，忽略或拒绝客户端传入的同名字段；
- 同一请求重复提交会生成两条记录（本期不做幂等）；
- 写入成功后立即持久化，进程重启不丢失。

### 3.2 GET /records —— 条件查询与分页

**查询参数**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| type | string | 否 | 无 | `收入` 或 `支出`，其他值返回 422 |
| category | string | 否 | 无 | 精确匹配，去除首尾空格后比较 |
| start_date | string | 否 | 无 | 起始日期（含），`YYYY-MM-DD` |
| end_date | string | 否 | 无 | 结束日期（含），`YYYY-MM-DD` |
| page | integer | 否 | 1 | 页码，≥ 1 |
| page_size | integer | 否 | 20 | 每页条数，1～100 |

**响应：200 OK**

```json
{
  "items": [
    {
      "id": 2,
      "amount": 5000.00,
      "type": "收入",
      "category": "工资",
      "date": "2026-11-01",
      "created_at": "2026-11-01T01:00:00Z"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1,
  "total_pages": 1
}
```

**规则**：

- 多个筛选条件为“与”关系；
- 日期区间为闭区间；
- 默认排序：`record_date` 降序，日期相同按 `id` 降序；
- 页码超出范围时返回空 `items`，`total` 仍为真实总数；
- 无匹配数据返回 200 和空列表，不返回 404。

### 3.3 GET /summary —— 区间汇总

**查询参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| start_date | string | 是 | 起始日期（含） |
| end_date | string | 是 | 结束日期（含） |

**响应：200 OK**

```json
{
  "start_date": "2026-11-01",
  "end_date": "2026-11-30",
  "income_total": 8000.00,
  "expense_total": 2350.75,
  "balance": 5649.25
}
```

**规则**：

- `income_total` 为区间内所有“收入”之和；
- `expense_total` 为区间内所有“支出”之和；
- `balance = income_total - expense_total`，保留 2 位小数；
- 区间内无记录时三项金额均为 `0.00`，仍返回 200；
- 起止日期均为必填，且 `start_date ≤ end_date`。

---

## 4. 校验规则

| 对象 | 规则 | 失败结果 |
|---|---|---|
| amount | 必须是数字；`0 < amount ≤ 99999999.99`；小数位 ≤ 2；拒绝 NaN、Infinity、布尔值、空字符串 | 422 + `amount` 错误说明 |
| type | 必须是 `收入` 或 `支出`，区分中文全角/半角，不接受英文或其他值 | 422 + 枚举错误说明 |
| category | 去除首尾空格后长度 1～50；不允许纯空白；不允许控制字符 | 422 + `category` 错误说明 |
| date | 严格 `YYYY-MM-DD`；必须是真实日期（如 2026-02-30 非法）；范围 2000-01-01～2100-12-31 | 422 + `date` 错误说明 |
| page | 整数，≥ 1 | 422 |
| page_size | 整数，1～100 | 422 |
| start_date / end_date | 格式与范围同上；查询时 `start_date ≤ end_date` | 422 + `INVALID_DATE_RANGE` |
| 未知字段 | POST 请求体中出现未定义字段 | 422，提示不支持的字段 |
| 未知路由 / 方法 | 访问不存在的路径或方法 | 404 / 405 |

校验顺序：先做类型与格式校验，再做业务范围校验；一次性返回全部字段错误，而不是只报第一个。

---

## 5. 错误规范

统一错误响应结构：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请求参数校验失败",
    "details": [
      {"field": "amount", "message": "金额必须大于 0"}
    ],
    "request_id": "8f3c2a1b"
  }
}
```

| HTTP 状态 | code | 场景 |
|---|---|---|
| 422 | `VALIDATION_ERROR` | 字段类型、格式、范围、枚举不合法 |
| 422 | `INVALID_DATE_RANGE` | `start_date` 晚于 `end_date` |
| 404 | `NOT_FOUND` | 路由不存在 |
| 405 | `METHOD_NOT_ALLOWED` | 方法不支持 |
| 503 | `DB_BUSY` | SQLite 写锁等待超时，重试 3 次仍失败 |
| 500 | `INTERNAL_ERROR` | 未预期异常，响应中不暴露堆栈 |

要求：

- 错误响应必须包含 `code`、`message`、`details`、`request_id`；
- `details` 为数组，可同时返回多个字段错误；
- 服务端日志记录 `request_id` 与异常堆栈，响应中只给安全信息；
- 不返回 HTML 错误页，不返回数据库原始错误文本。

---

## 6. 验收标准

| 编号 | 验收场景 | 通过标准 |
|---|---|---|
| AC-01 | 新增合法支出 | 返回 201，响应含 id、created_at，字段与请求一致 |
| AC-02 | 新增合法收入 | 同上，type 正确持久化 |
| AC-03 | amount = 0 / -1 / 1.999 / "abc" / NaN | 均返回 422，details 指明 amount |
| AC-04 | type 传“借”或“income” | 返回 422，提示仅允许收入/支出 |
| AC-05 | date 传 2026-02-30、2026/11/20、空值 | 均返回 422，details 指明 date |
| AC-06 | category 为空白或超过 50 字 | 返回 422 |
| AC-07 | 无筛选查询 | 返回默认第 1 页、每页 20 条，total 正确 |
| AC-08 | 按 type + category + 日期区间组合筛选 | 只返回同时满足条件的记录，日期边界包含在内 |
| AC-09 | 分页第 2 页与超范围页码 | 第 2 页数据正确；超范围返回空 items，total 不变 |
| AC-10 | page = 0 或 page_size = 101 | 返回 422 |
| AC-11 | start_date 晚于 end_date | 返回 422 `INVALID_DATE_RANGE` |
| AC-12 | 汇总区间含收入与支出 | income_total、expense_total、balance 计算正确，balance = 收入 - 支出 |
| AC-13 | 汇总区间无记录 | 三项金额均为 0.00，返回 200 |
| AC-14 | 金额精度 | 0.1 + 0.2 类场景按分计算，结果为 0.30，无浮点误差 |
| AC-15 | 并发写入 | 20 个并发 POST 全部成功或明确失败，成功的记录数、明细合计与汇总一致，无丢失、无重复 |
| AC-16 | 进程重启 | SQLite 文件保留，重启后可查询到此前记录 |
| AC-17 | 错误结构 | 所有 4xx/5xx 响应均为统一 JSON 结构，含 code、message、details、request_id |
| AC-18 | 文档可访问 | `/docs` 可打开，三个接口的请求/响应模型完整 |

**验收方式**：pytest + FastAPI TestClient 覆盖 AC-01～AC-14、AC-17、AC-18；并发用例使用线程池或 httpx 并发请求验证 AC-15；重启验证 AC-16。

---

## 7. 待确认项

| 编号 | 问题 | 默认方案（未确认时按此执行） |
|---|---|---|
| Q-01 | 是否需要用户登录与多用户数据隔离 | 本期不做，单用户 |
| Q-02 | category 是自由文本还是固定分类表 | 自由文本，长度 1～50 |
| Q-03 | 是否需要修改、删除流水 | 本期不做，仅新增与查询 |
| Q-04 | 是否需要幂等键防止重复提交 | 本期不做，客户端自行避免重试 |
| Q-05 | 汇总接口是否允许不传日期 | 必须传，避免全表扫描 |
| Q-06 | 金额是否允许超过 2 位小数 | 不允许，超过即 422 |

---

**确认方式**：由需求提出方逐项确认第 7 节；确认后本清单冻结为 V1.0，后续变更需记录版本与原因。
