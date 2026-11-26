# 实验一：Vibe Coding 双任务

> Excel 销售报表 + FastAPI 记账接口  
> 刘宝廷 ｜ 3242052051028 ｜ 软工24-2班

本实验包含两个互相独立的编码任务，均采用 Vibe Coding 方式与 AI 协作完成，可分别运行、分别验证。

## 目录结构

```
代码/
├── exam1_excel_report/        # 任务一：Excel 销售报表
│   ├── main.py                # 数据清洗 + 4 工作表报表
│   ├── test_report.py         # pytest 用例
│   ├── data/sales_raw.xlsx    # 输入样例
│   └── report.xlsx            # 生成结果
└── exam2_fastapi_account/     # 任务二：FastAPI 记账接口
    ├── main.py                # 3 个接口
    ├── database.py            # SQLAlchemy + SQLite
    └── test_api.py            # pytest 用例

运行截图/                       # 14 张运行与测试截图
实验报告-VibeCoding双任务.docx    # 完整实验报告
AI协作过程记录-VibeCoding双任务.docx
Vibe Coding 实验复盘.docx        # AI 与人工分工、风险审查
运行说明.docx                   # 详细运行步骤与常见问题
双任务流程图.png
需求澄清-Excel销售报表.md
需求澄清-FastAPI记账接口.md
requirements.txt
```

## 运行环境

- Python 3.10 及以上
- 在仓库根目录安装依赖：

```bash
pip install -r requirements.txt
```

## 任务一：Excel 销售报表

```bash
cd 代码/exam1_excel_report
python main.py
python -m pytest test_report.py -v
```

- 读取 `data/sales_raw.xlsx`，生成 `report.xlsx`，包含明细清洗后、按销售员、按地区、总览 4 个工作表。
- 预期结果：原始 14 行 → 有效 10 行，总销售额 960.00；pytest 6 passed。

## 任务二：FastAPI 记账接口

```bash
cd 代码/exam2_fastapi_account
uvicorn main:app --reload --port 8000
python -m pytest test_api.py -v
```

- 启动后访问 <http://127.0.0.1:8000/docs> 调试 3 个接口：`POST /records`、`GET /records`、`GET /summary`。
- 预期结果：新增返回 201；汇总收入 3500、支出 500、结余 3000；pytest 6 passed（测试使用内存 SQLite，不影响正式库）。

## 结果摘要

| 任务 | 验证项 | 结果 |
| --- | --- | --- |
| Excel | `python main.py` | 生成 report.xlsx，4 个工作表 |
| Excel | `pytest test_report.py -v` | 6 passed |
| FastAPI | `uvicorn main:app --port 8000` | 3 个接口可用，POST 返回 201 |
| FastAPI | `pytest test_api.py -v` | 6 passed |

> `.docx` 文件在 GitHub 上无法在线预览，点击文件后选择 Download 查看；实验报告内含完整过程、代码说明与运行截图。
