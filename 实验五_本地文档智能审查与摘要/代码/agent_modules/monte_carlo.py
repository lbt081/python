# -*- coding: utf-8 -*-
"""模块一：蒙特卡洛模拟关键词出现概率。

作用：
    把“关键词是否出现在某篇文档中”看作一个不确定事件，通过有放回抽样
    （bootstrap）模拟“随机抽取一篇文档”时包含该关键词的概率，输出均值、
    标准差、95% 区间和概率分布直方图数据，可作为大模型摘要模块的补充上下文。

运行示例（在项目根目录执行）：
    python agent_modules/monte_carlo.py --folder "示例文本" --keyword "自然语言处理" --simulations 10000 --plot
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_OUTPUT = "monte_carlo_result.json"

# 这些是分析工具的控制文件或输出文件，不参与文档抽样
IGNORED_NAMES = {
    "user_dict.txt",
    "stopwords.txt",
    "document_analysis_report.txt",
    "llm_prompt.txt",
    "llm_review.md",
}

# 这些后缀通常是编辑器临时文件，不参与统计
IGNORED_SUFFIXES = {".tmp", ".swp", ".part", ".bak"}


def is_ignored(path: Path) -> bool:
    """判断文件是否属于控制文件、输出文件或临时文件。"""
    name = path.name
    if name in IGNORED_NAMES:
        return True
    if name.startswith(".") or name.startswith("~$"):
        return True
    return path.suffix.lower() in IGNORED_SUFFIXES


def read_documents(folder_path: str | Path) -> list[tuple[str, str]]:
    """
    读取文件夹及子目录中的 .txt/.md 文档。

    返回：
        [(相对路径, 文本内容), ...]；读取失败的文件会被跳过，程序不中断。
    """
    folder = Path(folder_path).expanduser()

    if not folder.exists():
        print(f"[错误] 文件夹不存在：{folder}")
        return []
    if not folder.is_dir():
        print(f"[错误] 传入路径不是文件夹：{folder}")
        return []

    try:
        all_files = sorted(folder.rglob("*"))
    except (OSError, RuntimeError) as exc:
        print(f"[错误] 遍历文件夹失败：{exc}")
        return []

    documents: list[tuple[str, str]] = []
    for path in all_files:
        relative_name = path.name
        try:
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".txt", ".md"}:
                continue
            if is_ignored(path):
                continue

            relative_name = path.relative_to(folder).as_posix()
            text = path.read_text(encoding="utf-8-sig")

        except FileNotFoundError:
            print(f"[跳过] 文件不存在：{path}")
        except UnicodeDecodeError:
            print(f"[跳过] 编码错误，文件不是 UTF-8：{path}")
        except OSError as exc:
            print(f"[跳过] 读取失败：{path}，原因：{exc}")
        except Exception as exc:
            print(f"[跳过] 未知错误：{path}，原因：{exc}")
        else:
            documents.append((relative_name, text))
            print(f"[读取] {relative_name}")

    return documents


def percentile(sorted_values: list[float], percent: float) -> float:
    """
    计算百分位数（线性插值）。

    参数：
        sorted_values：已经升序排序的数值列表。
        percent：0～100 之间的百分位。
    """
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]

    position = (len(sorted_values) - 1) * percent / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return sorted_values[int(position)]

    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def run_simulation(
    keyword: str,
    documents: list[tuple[str, str]],
    simulations: int,
    seed: int,
) -> dict:
    """
    执行蒙特卡洛模拟。

    概率定义：
        从文档集合中有放回地随机抽取一篇文档，该文档包含关键词的概率。
    """
    keyword = keyword.strip()
    if not keyword:
        raise ValueError("关键词不能为空")
    if not documents:
        raise ValueError("没有可用于模拟的文档")
    if simulations < 1:
        raise ValueError("模拟次数必须大于 0")

    # 每篇文档是否包含关键词，1 表示包含，0 表示不包含
    indicators = [1 if keyword in text else 0 for _, text in documents]
    document_count = len(indicators)
    containing_count = sum(indicators)
    observed_probability = containing_count / document_count

    rng = random.Random(seed)
    samples: list[float] = []

    # 有放回抽样：每次模拟抽取 document_count 篇文档，计算包含关键词的比例
    for _ in range(simulations):
        hits = sum(indicators[rng.randrange(document_count)] for _ in range(document_count))
        samples.append(hits / document_count)

    samples.sort()
    mean = statistics.fmean(samples)
    std = statistics.pstdev(samples) if len(samples) > 1 else 0.0
    p2_5 = percentile(samples, 2.5)
    median = percentile(samples, 50)
    p97_5 = percentile(samples, 97.5)

    # 把 0～1 分成 20 个区间，供报告或绘图使用
    bin_count = 20
    bins = [round(index / bin_count, 2) for index in range(bin_count + 1)]
    counts = [0] * bin_count
    for value in samples:
        index = min(int(value * bin_count), bin_count - 1)
        counts[index] += 1

    result = {
        "keyword": keyword,
        "probability_definition": "从文档集合中有放回抽样，估计随机文档包含关键词的概率",
        "document_count": document_count,
        "documents_containing_keyword": containing_count,
        "observed_probability": round(observed_probability, 6),
        "simulations": simulations,
        "seed": seed,
        "mean": round(mean, 6),
        "std": round(std, 6),
        "min": round(min(samples), 6),
        "max": round(max(samples), 6),
        "percentile_2_5": round(p2_5, 6),
        "median": round(median, 6),
        "percentile_97_5": round(p97_5, 6),
        "ci_95": [round(p2_5, 6), round(p97_5, 6)],
        "histogram": {"bins": bins, "counts": counts},
        "documents": [name for name, _ in documents],
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return result


def save_result(result: dict, output_path: str | Path) -> Path | None:
    """把模拟结果保存为 UTF-8 JSON。"""
    output = Path(output_path).expanduser()
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except (OSError, UnicodeError) as exc:
        print(f"[错误] 结果保存失败：{output}，原因：{exc}")
        return None

    print(f"[成功] 模拟结果已保存：{output}")
    return output


def plot_histogram(result: dict, output_path: str | Path) -> Path | None:
    """可选：用 matplotlib 绘制概率分布直方图。"""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("[提示] 未安装 matplotlib，跳过直方图绘制。")
        return None

    bins = result["histogram"]["bins"]
    counts = result["histogram"]["counts"]

    try:
        output = Path(output_path).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)

        plt.figure(figsize=(8, 5))
        plt.bar(
            [bins[index] for index in range(len(counts))],
            counts,
            width=1 / len(counts),
            align="edge",
            color="#2E75B6",
            edgecolor="white",
        )
        plt.xlabel("Probability")
        plt.ylabel("Frequency")
        plt.title("Monte Carlo Probability Distribution")
        plt.tight_layout()
        plt.savefig(output, dpi=150)
        plt.close()
    except Exception as exc:
        print(f"[提示] 直方图绘制失败：{exc}")
        return None

    print(f"[成功] 直方图已保存：{output}")
    return output


def main() -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="蒙特卡洛模拟关键词出现概率")
    parser.add_argument("--folder", required=True, help="待分析文件夹")
    parser.add_argument("--keyword", required=True, help="要模拟的关键词")
    parser.add_argument("--simulations", type=int, default=10000, help="模拟次数，默认 10000")
    parser.add_argument("--seed", type=int, default=42, help="随机种子，默认 42")
    parser.add_argument("--output", default=None, help="JSON 输出路径，默认 <folder>/monte_carlo_result.json")
    parser.add_argument("--plot", action="store_true", help="同时生成概率分布直方图")
    args = parser.parse_args()

    print("=" * 60)
    print("蒙特卡洛模拟：关键词出现概率")
    print("=" * 60)

    documents = read_documents(args.folder)
    if not documents:
        print("[错误] 没有读取到可用的 .txt/.md 文档。")
        return 1

    try:
        result = run_simulation(
            keyword=args.keyword,
            documents=documents,
            simulations=args.simulations,
            seed=args.seed,
        )
    except ValueError as exc:
        print(f"[错误] {exc}")
        return 2

    result["source_folder"] = str(Path(args.folder).expanduser())
    output_path = (
        Path(args.output).expanduser()
        if args.output
        else Path(args.folder).expanduser() / DEFAULT_OUTPUT
    )
    output = save_result(result, output_path)

    print("\n---------------- 模拟结果 ----------------")
    print(f"关键词：{result['keyword']}")
    print(f"文档数：{result['document_count']}")
    print(f"包含关键词的文档数：{result['documents_containing_keyword']}")
    print(f"观测概率：{result['observed_probability']:.4f}")
    print(f"模拟次数：{result['simulations']}（seed={result['seed']}）")
    print(f"均值：{result['mean']:.4f}")
    print(f"标准差：{result['std']:.4f}")
    print(f"95% 区间：[{result['ci_95'][0]:.4f}, {result['ci_95'][1]:.4f}]")
    print(f"中位数：{result['median']:.4f}")

    if result["document_count"] < 10:
        print("[提示] 文档数较少，模拟结果的不确定性仅供参考。")
    if result["observed_probability"] in (0.0, 1.0):
        print("[提示] 关键词出现在全部或全部不包含于文档中，概率分布会退化为一个点。")

    if args.plot and output is not None:
        plot_histogram(result, output.with_name(output.stem + "_hist.png"))

    return 0 if output is not None else 1


if __name__ == "__main__":
    sys.exit(main())
