# 实验五：本地文档智能审查与摘要

> 刘宝廷 ｜ 3242052051028 ｜ 软工24-2班

对本地 `.txt` / `.md` 文档做中文分词与词频统计，并在此基础上实现三个 Agent：蒙特卡洛关键词概率模拟、大模型摘要（支持 dry-run / mock）、watchdog 文件夹自动监控。基础分析无需联网和 API Key。

## 目录结构

```
代码/
├── batch_read_text.py         # 基础分析入口：递归读取、分词、Top 词、词云、报告
├── agent_modules/
│   ├── monte_carlo.py         # Agent 1：蒙特卡洛模拟关键词出现概率
│   ├── llm_summary.py         # Agent 2：组装 Prompt 并调用大模型（支持 dry-run）
│   └── watch_folder.py        # Agent 3：watchdog 监控文件夹，新增文档自动分析
└── 示例文本/
    ├── 文章一.txt
    ├── 子目录/文章二.md
    ├── bad.txt                # 故意准备的 GBK 文件，用于演示编码异常
    ├── user_dict.txt          # 自定义词典
    └── stopwords.txt          # 停用词表

示例输出/                       # 参考输出（报告、词云、JSON、Prompt、Review）
运行截图/                       # 12 张逐步运行截图
实验报告-本地文档智能审查与摘要.docx
AI协作过程记录-本地文档智能审查与摘要.docx
运行说明.docx
文档分析流程图.png
requirements.txt
```

## 运行环境

```bash
pip install -r requirements.txt
```

## 基础分析

```bash
cd 代码
python batch_read_text.py
```

- 默认读取 `代码/示例文本`，生成 `document_analysis_report.txt` 和 `document_wordcloud.png`。
- 预期结果：成功 2、跳过 1（`bad.txt` 编码错误，属正常演示）、排除 2、失败 0；有效词汇 13，不同词汇 10；Top 词“机器学习 / 人工智能 / 自然语言处理”各 2 次。

## 三个 Agent

以下命令均在 `代码` 目录执行。

```bash
# Agent 1：蒙特卡洛模拟（10000 次，seed=42）
python agent_modules/monte_carlo.py --folder "示例文本" --keyword "自然语言处理" --simulations 10000 --plot

# Agent 2：大模型摘要，仅组装 Prompt，不需要 API Key
python agent_modules/llm_summary.py --folder "示例文本" --dry-run

# Agent 3：监控文件夹，新增 .txt/.md 后自动分析
python agent_modules/watch_folder.py --folder "示例文本" --debounce 2
```

| 模块 | 预期输出 |
| --- | --- |
| 蒙特卡洛 | 均值 0.49695、标准差 0.3546、95% 区间 [0, 1]，JSON + 直方图 |
| LLM 摘要 | dry-run 生成 `llm_prompt.txt`；配置 Key 后生成 `llm_review.md` |
| 文件夹监控 | 启动后分析已有文件，新增 txt/md 自动触发 |

## 真实大模型调用（可选）

本次实验验收只使用 dry-run 和本地 mock，未用真实 Key 调用外部 API。如需真实调用：

```powershell
$env:LLM_API_KEY="sk-..."
$env:LLM_BASE_URL="https://api.openai.com/v1"
$env:LLM_MODEL="gpt-4o-mini"
python agent_modules/llm_summary.py --folder "示例文本"
```

不要把 API Key 写入代码或提交到仓库。

> `.docx` 文件在 GitHub 上无法在线预览，点击文件后选择 Download 查看；实验报告内含完整设计、结果与截图。
