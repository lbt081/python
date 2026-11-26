# -*- coding: utf-8 -*-
"""模块二：调用大模型 API 生成结构化文档审查意见与摘要。

作用：
    1. 复用基础分析工具，得到 Top 50 关键词、词频和文件状态；
    2. 从原文中抽取关键词密度较高的句子，作为“清洗后的核心文本片段”；
    3. 读取模块一生成的蒙特卡洛结果，作为补充上下文；
    4. 组装 Prompt，调用 OpenAI 兼容的 Chat Completions API；
    5. 把模型返回的结构化审查意见保存为 Markdown 文件。

API Key 只从环境变量读取，代码中不保存真实 Key。

运行示例（在项目根目录执行）：
    python agent_modules/llm_summary.py --folder "示例文本" --dry-run
    python agent_modules/llm_summary.py --folder "示例文本"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError as exc:
    raise ImportError("未安装 requests，请先执行：pip install requests") from exc

# 让本模块可以导入项目根目录下的 batch_read_text.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from batch_read_text import analyze_texts, read_text_files
except ImportError as exc:
    raise ImportError(
        "无法导入 batch_read_text.py，请确保它与 agent_modules 目录在同一项目根目录"
    ) from exc


# 只从环境变量读取，禁止在代码中写死真实 Key
API_KEY_ENV = "LLM_API_KEY"
BASE_URL_ENV = "LLM_BASE_URL"
MODEL_ENV = "LLM_MODEL"

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"

SYSTEM_PROMPT = (
    "你是一名严谨的中文文档审查专家，擅长从词频统计和文本片段中提炼主题、"
    "发现内容风险，并给出可执行的修改建议。请只依据用户提供的材料分析，"
    "不要编造材料中没有出现的事实。输出必须使用中文，结构清晰。"
)


def build_exclude_paths(folder: Path, prompt_path: Path, review_path: Path) -> set[Path]:
    """构造不参与分析的路径集合，避免控制文件和输出文件污染词频。"""
    return {
        (folder / "user_dict.txt").resolve(),
        (folder / "stopwords.txt").resolve(),
        (folder / "document_analysis_report.txt").resolve(),
        (folder / "document_wordcloud.png").resolve(),
        prompt_path.resolve(),
        review_path.resolve(),
    }


def load_monte_carlo(path: str | Path | None) -> dict | None:
    """读取模块一生成的蒙特卡洛 JSON；失败时返回 None，不影响主流程。"""
    if not path:
        return None

    source = Path(path).expanduser()
    if not source.is_file():
        print(f"[提示] 未找到蒙特卡洛结果：{source}，将跳过补充上下文。")
        return None

    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        print(f"[提示] 蒙特卡洛结果不是 UTF-8 编码：{source}")
        return None
    except json.JSONDecodeError as exc:
        print(f"[提示] 蒙特卡洛结果不是合法 JSON：{source}，原因：{exc}")
        return None
    except OSError as exc:
        print(f"[提示] 蒙特卡洛结果读取失败：{source}，原因：{exc}")
        return None

    if not isinstance(data, dict):
        print(f"[提示] 蒙特卡洛结果结构异常：{source}")
        return None

    return data


def clean_fragment(text: str) -> str:
    """清洗文本片段：去掉图片、链接地址、Markdown 标题符号和多余空白。"""
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)          # 去掉图片
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)      # 链接只保留文字
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_core_snippets(
    file_texts: list[tuple[str, str]],
    global_top: list[tuple[str, int]],
    max_snippets: int = 8,
    max_chars: int = 3000,
) -> list[str]:
    """
    从原文中抽取关键词密度较高的句子，作为 Prompt 的核心文本片段。

    参数：
        file_texts：read_text_files 返回的 (相对路径, 文本) 列表。
        global_top：全局词频列表，通常取 Top 50。
        max_snippets：最多保留的片段数，默认 8。
        max_chars：片段总字符数上限，默认 3000。

    返回：
        带文件名前缀的文本片段列表。
    """
    keywords = [word for word, _ in global_top[:50] if len(word) >= 2]
    candidates: list[tuple[int, str, str]] = []

    for file_name, text in file_texts:
        cleaned = clean_fragment(text)
        # 按中英文句末标点和换行切分，保留较长的句子
        parts = re.split(r"[。！？!?；;\n]+", cleaned)

        for part in parts:
            sentence = re.sub(r"\s+", " ", part).strip(" #*-·")
            if len(sentence) < 15:
                continue

            # 用 Top 关键词命中次数给句子打分
            score = sum(sentence.count(word) for word in keywords)
            if score > 0:
                candidates.append((score, file_name, sentence))

    # 按得分从高到低排序，并做简单去重
    candidates.sort(key=lambda item: (-item[0], item[1]))
    selected: list[str] = []
    seen: set[str] = set()

    for _, file_name, sentence in candidates:
        key = sentence[:80]
        if key in seen:
            continue
        seen.add(key)
        selected.append(f"《{file_name}》：{sentence[:300]}")
        if len(selected) >= max_snippets:
            break

    # 如果没有任何句子命中关键词，退化为每个文件取开头一段
    if not selected:
        for file_name, text in file_texts[:3]:
            cleaned = clean_fragment(text)
            if cleaned:
                selected.append(f"《{file_name}》：{cleaned[:300]}")

    # 控制总长度，避免 Prompt 过长
    result: list[str] = []
    total_chars = 0
    for snippet in selected:
        if total_chars + len(snippet) > max_chars:
            break
        result.append(snippet)
        total_chars += len(snippet)

    return result


def build_prompt(
    result,
    snippets: list[str],
    monte_carlo: dict | None,
) -> tuple[str, str]:
    """把统计结果、蒙特卡洛上下文和核心片段组装成系统提示词与用户提示词。"""
    top_lines = "\n".join(
        f"{index}. {word}：{count}"
        for index, (word, count) in enumerate(result.global_top, start=1)
    ) or "（没有统计到有效关键词）"

    if monte_carlo:
        ci = monte_carlo.get("ci_95") or [None, None]
        monte_carlo_text = (
            f"关键词：{monte_carlo.get('keyword', '未知')}\n"
            f"观测概率：{monte_carlo.get('observed_probability')}\n"
            f"模拟均值：{monte_carlo.get('mean')}\n"
            f"95% 区间：{ci}\n"
            f"模拟次数：{monte_carlo.get('simulations')}"
        )
    else:
        monte_carlo_text = "未提供（可先运行 monte_carlo.py 生成补充上下文）"

    snippets_text = "\n".join(f"- {snippet}" for snippet in snippets) or "（没有可用片段）"

    success_count = sum(1 for item in result.file_statuses if item.status == "成功")
    skip_count = sum(1 for item in result.file_statuses if item.status == "跳过")

    user_prompt = f"""请根据下面的文档统计数据和核心片段，生成一份结构化的文档审查意见与摘要。

【文档概况】
分析目录：{result.folder_path}
成功读取文件：{success_count} 个
跳过文件：{skip_count} 个
有效词汇总数（含重复）：{result.total_words}
不同词汇数量：{result.unique_words}

【全局高频关键词及词频（最多 50 个）】
{top_lines}

【蒙特卡洛补充上下文】
{monte_carlo_text}

【清洗后的核心文本片段】
{snippets_text}

请严格按以下 Markdown 结构输出，不要省略任何一级标题：

# 文档审查意见与摘要

## 一、文档主题摘要
用 150 字左右概括文档主题和主要对象。

## 二、核心内容概述
分点概括文档的核心内容、结构和主要结论。

## 三、关键词与主题一致性
分析高频关键词是否支撑文档主题，指出可能的偏题或缺失。

## 四、风险与问题
列出内容层面可能存在的风险、歧义、缺失信息或表述问题。

## 五、修改建议
给出具体、可执行的修改建议，按优先级排序。

## 六、总体结论
给出总体评价，并说明适合的后续处理方式。
"""
    return SYSTEM_PROMPT, user_prompt


def call_llm(
    system_prompt: str,
    user_prompt: str,
    base_url: str,
    model: str,
    timeout: int = 120,
) -> str:
    """
    调用 OpenAI 兼容的 Chat Completions API。

    参数：
        system_prompt：系统提示词。
        user_prompt：用户提示词。
        base_url：API 基础地址，例如 https://api.deepseek.com/v1。
        model：模型名称，例如 deepseek-chat。
        timeout：请求超时时间，单位秒。

    返回：
        模型返回的文本内容。
    """
    api_key = os.getenv(API_KEY_ENV, "").strip()
    if not api_key:
        raise RuntimeError(
            f"未设置环境变量 {API_KEY_ENV}。\n"
            f'PowerShell 示例：$env:{API_KEY_ENV}="sk-你的Key"\n'
            f"CMD 示例：set {API_KEY_ENV}=sk-你的Key"
        )

    url = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 2000,
        "stream": False,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.Timeout as exc:
        raise RuntimeError(f"请求超时（{timeout} 秒）：{url}") from exc
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(f"无法连接 API：{url}") from exc
    except requests.exceptions.HTTPError as exc:
        # 只截取返回内容，避免把请求头或 Key 打印出来
        detail = response.text[:500] if response is not None else str(exc)
        raise RuntimeError(f"API 返回 HTTP 错误：{exc}；返回内容：{detail}") from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"API 请求失败：{exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("API 返回内容不是合法 JSON") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"API 返回结构异常：{str(data)[:500]}") from exc

    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("API 返回内容为空")

    usage = data.get("usage") or {}
    if usage:
        print(
            f"[提示] token 用量：prompt={usage.get('prompt_tokens')}，"
            f"completion={usage.get('completion_tokens')}，"
            f"total={usage.get('total_tokens')}"
        )

    return content.strip()


def main() -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="调用大模型生成文档审查意见与摘要")
    parser.add_argument("--folder", required=True, help="待分析文件夹")
    parser.add_argument("--output", default=None, help="审查意见输出路径，默认 <folder>/llm_review.md")
    parser.add_argument("--prompt-output", default=None, help="Prompt 输出路径，默认 <folder>/llm_prompt.txt")
    parser.add_argument("--monte-carlo", default=None, help="蒙特卡洛结果 JSON 路径")
    parser.add_argument("--top", type=int, default=50, help="送入 Prompt 的关键词数量，默认 50")
    parser.add_argument("--timeout", type=int, default=120, help="API 超时时间，默认 120 秒")
    parser.add_argument("--dry-run", action="store_true", help="只组装并保存 Prompt，不调用 API")
    parser.add_argument(
        "--base-url",
        default=os.getenv(BASE_URL_ENV, DEFAULT_BASE_URL),
        help=f"API 基础地址，默认读取 {BASE_URL_ENV} 或 {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--model",
        default=os.getenv(MODEL_ENV, DEFAULT_MODEL),
        help=f"模型名称，默认读取 {MODEL_ENV} 或 {DEFAULT_MODEL}",
    )
    args = parser.parse_args()

    folder = Path(args.folder).expanduser()
    if not folder.is_dir():
        print(f"[错误] 目标文件夹不存在或不是文件夹：{folder}")
        return 1

    review_path = Path(args.output) if args.output else folder / "llm_review.md"
    prompt_path = (
        Path(args.prompt_output)
        if args.prompt_output
        else folder / "llm_prompt.txt"
    )

    exclude_paths = build_exclude_paths(folder, prompt_path, review_path)

    print("=" * 60)
    print("大模型文档审查与摘要")
    print(f"目标目录：{folder}")
    print("=" * 60)

    try:
        result = analyze_texts(
            folder_path=folder,
            user_dict_path=(folder / "user_dict.txt") if (folder / "user_dict.txt").is_file() else None,
            stopwords_path=(folder / "stopwords.txt") if (folder / "stopwords.txt").is_file() else None,
            global_top_n=args.top,
            file_top_n=10,
            exclude_paths=exclude_paths,
        )
    except Exception as exc:
        print(f"[错误] 文档分析失败：{exc}")
        return 1

    # 重新读取原文，用于抽取核心片段；读取时会自动跳过控制文件和输出文件
    try:
        file_texts = read_text_files(folder, exclude_paths=exclude_paths)
    except Exception as exc:
        print(f"[错误] 读取原文失败：{exc}")
        return 1

    snippets = extract_core_snippets(file_texts, result.global_top)

    monte_carlo_path = (
        Path(args.monte_carlo)
        if args.monte_carlo
        else folder / "monte_carlo_result.json"
    )
    monte_carlo = load_monte_carlo(monte_carlo_path)

    system_prompt, user_prompt = build_prompt(result, snippets, monte_carlo)

    # 无论是否调用 API，都先保存 Prompt，便于审查和复现
    try:
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(
            "=== SYSTEM ===\n"
            + system_prompt
            + "\n\n=== USER ===\n"
            + user_prompt,
            encoding="utf-8",
        )
    except (OSError, UnicodeError) as exc:
        print(f"[错误] Prompt 保存失败：{prompt_path}，原因：{exc}")
        return 1

    print(f"[成功] Prompt 已保存：{prompt_path}")

    if args.dry_run:
        print("\n---------------- Prompt 预览 ----------------")
        print(user_prompt)
        print("\n[dry-run] 未调用大模型 API。")
        return 0

    try:
        review = call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            base_url=args.base_url,
            model=args.model,
            timeout=args.timeout,
        )
    except RuntimeError as exc:
        print(f"[错误] 大模型调用失败：{exc}")
        return 1

    try:
        review_path.parent.mkdir(parents=True, exist_ok=True)
        review_path.write_text(review, encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"[错误] 审查意见保存失败：{review_path}，原因：{exc}")
        return 1

    print(f"[成功] 审查意见已保存：{review_path}")
    print("\n---------------- 审查意见预览 ----------------")
    print(review[:1000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
