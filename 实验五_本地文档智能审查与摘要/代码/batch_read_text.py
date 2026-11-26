# -*- coding: utf-8 -*-
"""批量读取文本文件，完成中文分词、词频统计、词云展示和分析报告输出。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    import matplotlib.pyplot as plt
except ImportError as exc:
    raise ImportError("未安装 matplotlib，请先执行：pip install matplotlib") from exc

try:
    from wordcloud import WordCloud
except ImportError as exc:
    raise ImportError("未安装 wordcloud，请先执行：pip install wordcloud") from exc

try:
    import jieba
except ImportError as exc:
    raise ImportError("未安装 jieba，请先执行：pip install jieba") from exc


# 未提供 stopwords.txt 时使用的内置基础中文停用词
DEFAULT_STOPWORDS: set[str] = {
    "的", "了", "和", "是", "在", "我", "有", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
    "没有", "看", "好", "自己", "这", "那", "他", "她", "它", "们", "与",
    "及", "或", "而", "但", "因", "为", "所以", "如果", "已经", "可以",
    "进行", "通过", "以及", "等", "被", "把", "让", "从", "对", "中",
    "内", "外", "后", "前", "里", "时", "年", "月", "日", "个", "些",
    "什么", "怎么", "如何", "因为", "因此", "并且", "还是", "其实", "目前",
    "相关", "方面", "情况", "问题", "需要", "应该", "可能", "其中", "这种",
    "这些", "那些", "我们", "你们", "他们", "她们", "它们", "大家", "不是",
    "不能", "就是", "只是", "不过", "而且", "然后", "同时", "另外", "此外",
    "例如", "比如", "等等", "对于", "关于", "由于", "地", "得", "过",
    "吗", "呢", "吧", "啊", "呀", "哦", "嗯",
}


@dataclass
class FileStatus:
    """单个文件的处理状态。"""

    file_name: str
    status: str          # 成功 / 跳过 / 排除 / 失败
    message: str = ""


@dataclass
class AnalysisResult:
    """一次完整分析的结果，供控制台输出、词云和报告共用。"""

    folder_path: str
    file_statuses: list[FileStatus]
    total_words: int
    unique_words: int
    global_top: list[tuple[str, int]]
    per_file_top: dict[str, list[tuple[str, int]]]
    user_dict_path: str | None = None
    stopwords_path: str | None = None
    generated_at: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


def read_text_files_with_status(
    folder_path: str | Path,
    exclude_paths: set[Path] | None = None,
) -> tuple[list[tuple[str, str]], list[FileStatus]]:
    """
    批量读取指定文件夹及其子目录下所有 .txt 和 .md 文件，并记录每个文件的状态。

    参数：
        folder_path：要遍历的文件夹路径，支持字符串或 Path 对象。
        exclude_paths：需要跳过的文件绝对路径集合，可选；
                       用于排除放在文本目录中的自定义词典、停用词表等控制文件。

    返回：
        ([(相对路径, 文本内容), ...], [FileStatus, ...])。
        读取失败的文件会记录为“跳过”，程序不会中断。
    """
    folder = Path(folder_path).expanduser()
    statuses: list[FileStatus] = []

    # 先校验文件夹本身，避免后续遍历时报错
    try:
        if not folder.exists():
            message = f"文件夹不存在：{folder}"
            print(f"[错误] {message}")
            statuses.append(FileStatus(str(folder), "失败", message))
            return [], statuses

        if not folder.is_dir():
            message = f"传入路径不是文件夹：{folder}"
            print(f"[错误] {message}")
            statuses.append(FileStatus(str(folder), "失败", message))
            return [], statuses
    except OSError as exc:
        message = f"无法访问文件夹：{folder}，原因：{exc}"
        print(f"[错误] {message}")
        statuses.append(FileStatus(str(folder), "失败", message))
        return [], statuses

    results: list[tuple[str, str]] = []
    target_suffixes = {".txt", ".md"}

    # 先收集全部文件路径；遍历时若遇到权限等错误，打印提示并安全返回
    try:
        all_files = sorted(folder.rglob("*"))
    except (OSError, RuntimeError) as exc:
        message = f"遍历文件夹失败：{exc}"
        print(f"[错误] {message}")
        statuses.append(FileStatus(str(folder), "失败", message))
        return [], statuses

    # 逐个读取，排序后处理，保证每次输出顺序一致
    for file_path in all_files:
        # 先给一个兜底名称；正常情况下会被相对路径覆盖
        relative_name = file_path.name

        try:
            # 相对路径在遍历阶段就能确定，异常处理时也可以使用
            relative_name = file_path.relative_to(folder).as_posix()

            # 只处理普通文件，且扩展名必须是 .txt 或 .md（不区分大小写）
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in target_suffixes:
                continue

            # 跳过调用方指定排除的控制文件（如自定义词典、停用词表）
            if exclude_paths and file_path.resolve() in exclude_paths:
                statuses.append(
                    FileStatus(relative_name, "排除", "按 exclude_paths 排除，未参与统计")
                )
                print(f"[排除] {relative_name}（按 exclude_paths 排除）")
                continue

            # 统一使用 UTF-8 编码读取；utf-8-sig 可兼容带 BOM 的文件
            text = file_path.read_text(encoding="utf-8-sig")

        except FileNotFoundError:
            # 遍历后文件被删除或移动时可能触发
            statuses.append(FileStatus(relative_name, "跳过", "文件不存在"))
            print(f"[跳过] 文件不存在：{file_path}")

        except UnicodeDecodeError:
            # 文件不是 UTF-8 编码时触发
            statuses.append(FileStatus(relative_name, "跳过", "编码错误，文件不是 UTF-8"))
            print(f"[跳过] 编码错误，文件不是 UTF-8：{file_path}")

        except OSError as exc:
            # 权限不足、磁盘错误、文件被占用等读取异常
            statuses.append(FileStatus(relative_name, "跳过", f"读取失败：{exc}"))
            print(f"[跳过] 读取失败：{file_path}，原因：{exc}")

        except Exception as exc:
            # 兜底捕获其他未知异常，保证单个文件出错不影响后续文件
            statuses.append(FileStatus(relative_name, "跳过", f"未知错误：{exc}"))
            print(f"[跳过] 未知错误：{file_path}，原因：{exc}")

        else:
            results.append((relative_name, text))
            statuses.append(FileStatus(relative_name, "成功", "已读取"))
            print(f"[成功] 已读取：{relative_name}")

    return results, statuses


def read_text_files(
    folder_path: str | Path,
    exclude_paths: set[Path] | None = None,
) -> list[tuple[str, str]]:
    """
    兼容旧用法的读取函数，只返回读取成功的 (相对路径, 文本内容) 列表。

    需要文件状态时请使用 read_text_files_with_status。
    """
    results, _ = read_text_files_with_status(folder_path, exclude_paths)
    return results


def load_stopwords(stopwords_path: str | Path | None = None) -> set[str]:
    """
    加载停用词表。

    参数：
        stopwords_path：停用词文件路径，每行一个词；为 None 时使用内置停用词。

    返回：
        停用词集合。文件不存在、编码错误、读取失败或内容为空时，回退到内置停用词。
    """
    # 未提供文件时直接使用内置停用词
    if stopwords_path is None:
        print("[提示] 未提供停用词文件，使用内置基础中文停用词。")
        return set(DEFAULT_STOPWORDS)

    try:
        path = Path(stopwords_path).expanduser()
    except (TypeError, OSError) as exc:
        print(f"[提示] 停用词路径无效：{stopwords_path}，原因：{exc}，使用内置基础中文停用词。")
        return set(DEFAULT_STOPWORDS)

    try:
        # utf-8-sig 可以兼容带 BOM 的 UTF-8 文件
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        print(f"[提示] 停用词文件不存在：{path}，使用内置基础中文停用词。")
        return set(DEFAULT_STOPWORDS)
    except UnicodeDecodeError:
        print(f"[提示] 停用词文件不是 UTF-8 编码：{path}，使用内置基础中文停用词。")
        return set(DEFAULT_STOPWORDS)
    except OSError as exc:
        print(f"[提示] 停用词文件读取失败：{path}，原因：{exc}，使用内置基础中文停用词。")
        return set(DEFAULT_STOPWORDS)
    except Exception as exc:
        print(f"[提示] 停用词文件读取异常：{path}，原因：{exc}，使用内置基础中文停用词。")
        return set(DEFAULT_STOPWORDS)

    # 逐行去除首尾空白，忽略空行
    stopwords = {line.strip() for line in lines if line.strip()}

    # 文件存在但内容为空时也回退到内置集合，避免完全不过滤停用词
    if not stopwords:
        print(f"[提示] 停用词文件为空：{path}，使用内置基础中文停用词。")
        return set(DEFAULT_STOPWORDS)

    print(f"[提示] 已加载停用词 {len(stopwords)} 个：{path}")
    return stopwords


def load_user_dict(user_dict_path: str | Path | None = None) -> bool:
    """
    加载 jieba 自定义词典。

    参数：
        user_dict_path：词典文件路径，每行格式为“词语 词频 词性”，词频和词性可省略；
                        为 None 时不加载。

    返回：
        加载成功返回 True，未提供或加载失败返回 False。
    """
    # 未提供词典时使用 jieba 自带词典
    if user_dict_path is None:
        print("[提示] 未提供自定义词典，使用 jieba 默认词典。")
        return False

    try:
        path = Path(user_dict_path).expanduser()
    except (TypeError, OSError) as exc:
        print(f"[提示] 自定义词典路径无效：{user_dict_path}，原因：{exc}，使用 jieba 默认词典。")
        return False

    # 文件不存在时给出提示，但继续使用默认词典
    if not path.is_file():
        print(f"[提示] 自定义词典不存在：{path}，使用 jieba 默认词典。")
        return False

    try:
        jieba.load_userdict(str(path))
    except UnicodeDecodeError:
        print(f"[提示] 自定义词典不是 UTF-8 编码：{path}，使用 jieba 默认词典。")
        return False
    except OSError as exc:
        print(f"[提示] 自定义词典读取失败：{path}，原因：{exc}，使用 jieba 默认词典。")
        return False
    except Exception as exc:
        print(f"[提示] 自定义词典加载失败：{path}，原因：{exc}，使用 jieba 默认词典。")
        return False

    print(f"[提示] 已加载自定义词典：{path}")
    return True


def tokenize_text(text: str, stopwords: set[str]) -> list[str]:
    """
    使用 jieba 精确模式分词，并过滤停用词、单字词和纯标点。

    参数：
        text：待分词的文本。
        stopwords：停用词集合。

    返回：
        过滤后的词语列表。
    """
    # jieba.lcut 默认就是精确模式，这里显式写出 cut_all=False 便于阅读
    words = jieba.lcut(text, cut_all=False)

    result: list[str] = []
    for word in words:
        word = word.strip()

        # 跳过空串、单字词（长度为 1）和停用词
        if not word or len(word) < 2 or word in stopwords:
            continue

        # 跳过纯标点、空格等非字母数字词，避免标点进入词频
        if not word.isalnum():
            continue

        result.append(word)

    return result


def analyze_texts(
    folder_path: str | Path,
    user_dict_path: str | Path | None = None,
    stopwords_path: str | Path | None = None,
    global_top_n: int = 50,
    file_top_n: int = 10,
    exclude_paths: set[Path] | None = None,
) -> AnalysisResult:
    """
    读取文件夹中的 .txt 和 .md 文件，完成分词、全局词频统计和单文件关键词提取。

    参数：
        folder_path：待读取的文件夹路径。
        user_dict_path：自定义词典路径，可为 None。
        stopwords_path：停用词表路径，可为 None；None 或读取失败时使用内置停用词。
        global_top_n：全局词频返回条数，默认 50。
        file_top_n：每个文件关键词返回条数，默认 10。
        exclude_paths：额外需要排除的文件路径集合，例如上一次生成的报告文件。

    返回：
        AnalysisResult 对象，包含文件状态、总词汇量、全局 Top N 和单文件 Top N。
    """
    folder = Path(folder_path).expanduser()

    # Top N 参数兜底，避免传入 0 或负数导致结果为空
    if global_top_n < 1:
        print("[提示] global_top_n 必须大于 0，已改为默认值 50。")
        global_top_n = 50
    if file_top_n < 1:
        print("[提示] file_top_n 必须大于 0，已改为默认值 10。")
        file_top_n = 10

    # 如果词典或停用词表放在文本目录中，读取时要排除，避免它们被当作正文统计
    excluded_paths: set[Path] = set()
    for path_value in (user_dict_path, stopwords_path, *(exclude_paths or set())):
        if path_value is not None:
            try:
                excluded_paths.add(Path(path_value).expanduser().resolve())
            except (TypeError, OSError, RuntimeError) as exc:
                print(f"[提示] 控制文件路径无效：{path_value}，原因：{exc}")

    # 读取文件并保留每个文件的状态，供报告使用
    file_texts, statuses = read_text_files_with_status(
        folder,
        exclude_paths=excluded_paths,
    )

    if not file_texts:
        print("[提示] 没有可分析的文本文件（文件夹为空或全部读取失败）。")

    # 加载自定义词典和停用词；函数内部会处理常见的缺失和编码错误
    try:
        load_user_dict(user_dict_path)
        stopwords = load_stopwords(stopwords_path)
    except Exception as exc:
        print(f"[提示] 词典或停用词加载异常，使用内置停用词：{exc}")
        stopwords = set(DEFAULT_STOPWORDS)

    global_counter: Counter[str] = Counter()
    per_file_top: dict[str, list[tuple[str, int]]] = {}

    # 逐个文件分词、统计
    for file_name, text in file_texts:
        try:
            words = tokenize_text(text, stopwords)
        except Exception as exc:
            # 单个文件分词失败时，把它标记为跳过，继续处理其他文件
            print(f"[跳过] 分词失败：{file_name}，原因：{exc}")
            for status in statuses:
                if status.file_name == file_name:
                    status.status = "跳过"
                    status.message = f"分词失败：{exc}"
                    break
            continue

        # 累加到全局词频
        global_counter.update(words)

        # 当前文件单独统计，取 Top N
        per_file_top[file_name] = Counter(words).most_common(file_top_n)

    total_words = sum(global_counter.values())
    if total_words == 0:
        print("[提示] 所有文件均未统计到有效词汇（可能全部是停用词、单字或标点）。")

    return AnalysisResult(
        folder_path=str(folder),
        file_statuses=statuses,
        total_words=total_words,
        unique_words=len(global_counter),
        global_top=global_counter.most_common(global_top_n),
        per_file_top=per_file_top,
        user_dict_path=str(user_dict_path) if user_dict_path else None,
        stopwords_path=str(stopwords_path) if stopwords_path else None,
    )


def find_chinese_font() -> str:
    """
    查找常见的中文字体文件。

    返回：
        字体文件路径。找不到时抛出 FileNotFoundError，提示手动指定 font_path。
    """
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\Deng.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]

    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            return str(path)

    raise FileNotFoundError(
        "未找到可用的中文字体，请在 generate_wordcloud 中手动指定 font_path，"
        "例如 C:\\Windows\\Fonts\\msyh.ttc"
    )


def generate_wordcloud(
    global_top: list[tuple[str, int]],
    output_path: str | Path = "document_wordcloud.png",
    font_path: str | Path | None = None,
    show: bool = True,
) -> Path | None:
    """
    根据全局高频词生成词云，保存为 PNG，并用 matplotlib 弹窗展示。

    参数：
        global_top：[(词语, 词频), ...]，通常传入 Top 50。
        output_path：词云图片保存路径，默认 document_wordcloud.png。
        font_path：中文字体路径；为 None 时自动查找常见中文字体。
        show：是否弹窗显示，默认 True；无图形界面或批量运行时可以设为 False。

    返回：
        保存成功的图片路径；没有可绘制词汇、字体缺失或保存失败时返回 None。
    """
    if output_path is None:
        print("[错误] 词云输出路径不能为空。")
        return None

    # 过滤非正数词频，避免 WordCloud 无法生成
    frequencies = {word: count for word, count in global_top if count > 0}
    if not frequencies:
        print("[提示] 没有可绘制的高频词，跳过词云生成。")
        return None

    # 未指定字体时自动查找；找不到时给出明确提示，不中断报告生成
    if font_path is None:
        try:
            font_path = find_chinese_font()
        except FileNotFoundError as exc:
            print(f"[错误] 词云生成失败：{exc}")
            return None

    font = Path(font_path).expanduser()
    if not font.is_file():
        print(f"[错误] 字体文件不存在：{font}")
        print('       请修改 font_path，例如 r"C:\\Windows\\Fonts\\msyh.ttc"')
        return None

    # 如果生成的词云显示方框，通常是字体不含中文字形，请换用 msyh.ttc 或 simhei.ttf

    try:
        # 按题目要求设置白底、1000×800、最多 50 个词、关闭词语搭配
        wordcloud = WordCloud(
            font_path=str(font),
            background_color="white",
            width=1000,
            height=800,
            max_words=50,
            collocations=False,
        )

        # 直接按“词语: 词频”生成，不再对原文重新分词
        wordcloud.generate_from_frequencies(frequencies)
    except Exception as exc:
        print(f"[错误] 词云生成失败：{exc}")
        return None

    output = Path(output_path).expanduser()
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        wordcloud.to_file(str(output))
    except (OSError, ValueError) as exc:
        print(f"[错误] 词云图片保存失败：{output}，原因：{exc}")
        return None

    print(f"[成功] 词云已保存：{output}")

    # 用 matplotlib 弹窗展示词云；显示失败不影响已保存的图片
    try:
        plt.figure(figsize=(10, 8), dpi=100)
        plt.imshow(wordcloud, interpolation="bilinear")
        plt.axis("off")
        plt.tight_layout(pad=0)

        if show:
            plt.show()
    except Exception as exc:
        print(f"[提示] 词云弹窗显示失败（图片已保存）：{exc}")
    finally:
        plt.close()

    return output


def write_report(
    result: AnalysisResult,
    output_path: str | Path = "document_analysis_report.txt",
) -> Path | None:
    """
    将分析结果写入 UTF-8 编码的文本报告。

    报告内容包括：
        1. 处理文件列表及状态；
        2. 总词汇量；
        3. 全局 Top 50 词频明细；
        4. 每个文件的 Top 10 关键词。

    参数：
        result：analyze_texts 返回的分析结果。
        output_path：报告保存路径，默认 document_analysis_report.txt。

    返回：
        报告文件路径；保存失败时返回 None。
    """
    if output_path is None:
        print("[错误] 报告输出路径不能为空。")
        return None

    output = Path(output_path).expanduser()

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("文档分词与词频分析报告")
    lines.append("=" * 60)
    lines.append(f"生成时间：{result.generated_at}")
    lines.append(f"分析目录：{result.folder_path}")
    lines.append(f"自定义词典：{result.user_dict_path or '未使用'}")
    lines.append(f"停用词表：{result.stopwords_path or '未使用（使用内置停用词）'}")
    lines.append("")

    # 一、处理文件列表及状态
    lines.append("一、处理文件列表及状态")
    lines.append("-" * 60)
    if result.file_statuses:
        for status in result.file_statuses:
            message = f"：{status.message}" if status.message else ""
            lines.append(f"[{status.status}] {status.file_name}{message}")
    else:
        lines.append("未发现 .txt 或 .md 文件。")

    success_count = sum(1 for item in result.file_statuses if item.status == "成功")
    skip_count = sum(1 for item in result.file_statuses if item.status == "跳过")
    exclude_count = sum(1 for item in result.file_statuses if item.status == "排除")
    fail_count = sum(1 for item in result.file_statuses if item.status == "失败")

    lines.append("")
    lines.append(
        f"统计：成功 {success_count} 个，跳过 {skip_count} 个，"
        f"排除 {exclude_count} 个，失败 {fail_count} 个。"
    )
    lines.append("")

    # 二、总词汇量
    lines.append("二、总词汇量")
    lines.append("-" * 60)
    lines.append(f"有效词汇总数（含重复）：{result.total_words}")
    lines.append(f"不同词汇数量：{result.unique_words}")
    lines.append("")

    # 三、全局 Top 50 词频明细
    lines.append("三、全局 Top 50 词频明细")
    lines.append("-" * 60)
    if result.global_top:
        for rank, (word, count) in enumerate(result.global_top, start=1):
            lines.append(f"{rank:>3}. {word}  {count}")
    else:
        lines.append("没有统计到有效词汇。")
    lines.append("")

    # 四、各文件 Top 10 关键词
    lines.append("四、各文件 Top 10 关键词")
    lines.append("-" * 60)
    if result.per_file_top:
        for file_name, keywords in result.per_file_top.items():
            lines.append(f"【{file_name}】")
            if keywords:
                for rank, (word, count) in enumerate(keywords, start=1):
                    lines.append(f"  {rank:>2}. {word}  {count}")
            else:
                lines.append("  （没有统计到有效词汇）")
            lines.append("")
    else:
        lines.append("没有可统计的文件。")
        lines.append("")

    lines.append("=" * 60)
    lines.append("报告结束")
    lines.append("=" * 60)

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(lines), encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"[错误] 分析报告保存失败：{output}，原因：{exc}")
        return None

    print(f"[成功] 分析报告已保存：{output}")
    return output


def main() -> None:
    """完整流程：读取文件 → 分词统计 → 生成词云 → 输出报告。"""
    # ==================== 路径配置：使用时只需修改这里 ====================
    # target_folder：待分析的 .txt / .md 文件夹，支持子目录
    # user_dict_path：自定义词典路径，没有就设为 None
    # stopwords_path：停用词表路径，没有就设为 None（会自动使用内置停用词）
    # 词云和报告默认输出到 target_folder 下
    # 上一次生成的报告会在本次读取时自动排除，避免污染词频
    # 中文字体默认自动查找 msyh.ttc 等常见字体；
    # 如果自动查找失败，可在 generate_wordcloud(..., font_path=r"字体路径") 中手动指定
    # 以脚本所在目录为基准，保证整个文件夹复制到其他电脑后仍可运行
    target_folder = Path(__file__).resolve().parent / "示例文本"
    user_dict_path = target_folder / "user_dict.txt"
    stopwords_path = target_folder / "stopwords.txt"
    wordcloud_path = target_folder / "document_wordcloud.png"
    report_path = target_folder / "document_analysis_report.txt"
    # ====================================================================

    # 目标文件夹不存在时直接提示，避免在错误路径下创建空目录
    try:
        if not target_folder.is_dir():
            print(f"[错误] 目标文件夹不存在或不是文件夹：{target_folder}")
            print("请修改 main() 中的 target_folder 后重试。")
            return
    except OSError as exc:
        print(f"[错误] 无法访问目标文件夹：{target_folder}，原因：{exc}")
        return

    print("=" * 60)
    print("文档分词与词频分析")
    print(f"目标目录：{target_folder}")
    print("=" * 60)

    try:
        result = analyze_texts(
            folder_path=target_folder,
            user_dict_path=user_dict_path,
            stopwords_path=stopwords_path,
            global_top_n=50,
            file_top_n=10,
            # 排除上一次生成的报告和 LLM 输出，避免它们被当成正文参与分词
            exclude_paths={
                report_path,
                wordcloud_path,
                target_folder / "llm_prompt.txt",
                target_folder / "llm_review.md",
            },
        )
    except Exception as exc:
        print(f"[错误] 分析失败：{exc}")
        return

    # 控制台输出全局 Top 50
    print("\n================ 全局词频 Top 50 ================")
    if result.global_top:
        for rank, (word, count) in enumerate(result.global_top, start=1):
            print(f"{rank:>2}. {word:<12} {count}")
    else:
        print("（没有统计到有效词汇）")

    # 控制台输出每个文件的 Top 10
    print("\n================ 各文件 Top 10 关键词 ================")
    for file_name, keywords in result.per_file_top.items():
        print(f"\n[{file_name}]")
        if not keywords:
            print("  （没有统计到有效词汇）")
            continue
        for rank, (word, count) in enumerate(keywords, start=1):
            print(f"  {rank:>2}. {word:<12} {count}")

    # 生成词云；show=True 会弹出 matplotlib 窗口，不想弹窗时改为 False
    try:
        wordcloud_file = generate_wordcloud(
            result.global_top,
            output_path=wordcloud_path,
            show=True,
        )
    except Exception as exc:
        print(f"[错误] 词云生成失败：{exc}")
        wordcloud_file = None

    # 生成文本报告
    report_file = write_report(result, output_path=report_path)

    print("\n处理结束。")
    if wordcloud_file:
        print(f"词云图片：{wordcloud_file}")
    else:
        print("词云图片：未生成（无有效词汇，或字体/保存异常）")
    if report_file:
        print(f"分析报告：{report_file}")
    else:
        print("分析报告：未生成（请检查输出路径和权限）")


if __name__ == "__main__":
    main()
