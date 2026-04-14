import argparse
import os
import sys
import re
from dataclasses import dataclass
from pathlib import Path

import orjson


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "05_src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


REVIEW_FLAG_PATTERN = re.compile(r"^--R_(\d+)$")


@dataclass(frozen=True)
class WorkflowCliConfig:
    dataset_root: Path
    output_base: Path
    prompt_variant: str
    mode_label: str


@dataclass(frozen=True)
class WorkflowExecutionSummary:
    mode_label: str
    dataset_root: str
    prompt_variant: str
    reports_output_dir: str
    category: str
    product_id: str
    max_reviews: int | None
    overview: dict[str, int]
    normalization: dict[str, object] | None
    index_result: dict[str, object] | None
    analysis: dict[str, object]
    html_export_path: str | None


def _preprocess_argv(argv: list[str]) -> list[str]:
    normalized: list[str] = []
    for arg in argv:
        match = REVIEW_FLAG_PATTERN.match(arg)
        if match:
            normalized.extend(["--max-reviews", match.group(1)])
            continue
        normalized.append(arg)
    return normalized


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="一键运行 Decathlon VOC Analyzer 工作流")
    parser.add_argument("--cn", action="store_true", help="中文模式简写：等价于设置中文 dataset_root、中文 prompt_variant 和 CN 输出命名空间")
    parser.add_argument("--category", default="backpack", help="类目，例如 backpack")
    parser.add_argument("--product-id", default="backpack_010", help="商品 ID，例如 backpack_010")
    parser.add_argument("--dataset-root", default=None, help="可选，显式指定数据集根目录，例如 01_data/02_audit_zh_products/products")
    parser.add_argument("--prompt-variant", default=None, help="可选，显式指定提示词变体，例如 main、cn、zh-cn")
    parser.add_argument("--output-namespace", default=None, help="可选，输出命名空间目录，例如 CN；为空时写入默认 02_outputs 根目录")
    parser.add_argument("--max-reviews", type=int, default=None, help="限制参与分析的评论数量")
    parser.add_argument("--top-k-per-route", type=int, default=2, help="每个模态召回的证据数量")
    parser.add_argument("--questions-per-aspect", type=int, default=2, help="每个 aspect 生成的问题数量")
    parser.add_argument("--no-llm", action="store_true", help="禁用 LLM，使用本地启发式链路")
    parser.add_argument("--skip-normalize", action="store_true", help="跳过标准化落盘阶段")
    parser.add_argument("--skip-index", action="store_true", help="跳过索引构建阶段")
    parser.add_argument("--export-html", action="store_true", help="分析完成后顺带导出单商品 HTML 页面")
    parser.add_argument("--output-format", choices=["text", "json"], default="text", help="输出格式；批处理场景建议使用 json")
    parser.add_argument("--quiet", action="store_true", help="安静模式；text 输出下仅打印最终摘要")
    parser.epilog = "支持简写参数，例如: --R_5 表示只分析前 5 条评论"
    return parser.parse_args(_preprocess_argv(sys.argv[1:]))


def _resolve_dataset_root(args: argparse.Namespace) -> Path:
    if args.dataset_root:
        candidate = Path(args.dataset_root)
        return candidate if candidate.is_absolute() else (ROOT_DIR / candidate)
    if args.cn:
        return ROOT_DIR / "01_data" / "02_audit_zh_products" / "products"
    return ROOT_DIR / "01_data" / "01_raw_products" / "products"


def _resolve_output_base(args: argparse.Namespace) -> Path:
    namespace = args.output_namespace
    if namespace is None and args.cn:
        namespace = "CN"
    return ROOT_DIR / "02_outputs" / namespace if namespace else ROOT_DIR / "02_outputs"


def _resolve_prompt_variant(args: argparse.Namespace) -> str:
    from decathlon_voc_analyzer.prompts import normalize_prompt_variant

    if args.prompt_variant:
        return normalize_prompt_variant(args.prompt_variant)
    return normalize_prompt_variant("CN" if args.cn else "main")


def build_cli_config(args: argparse.Namespace) -> WorkflowCliConfig:
    dataset_root = _resolve_dataset_root(args)
    output_base = _resolve_output_base(args)
    prompt_variant = _resolve_prompt_variant(args)
    mode_label = "中文数据集" if prompt_variant == "CN" else "主项目原始数据集"
    return WorkflowCliConfig(
        dataset_root=dataset_root,
        output_base=output_base,
        prompt_variant=prompt_variant,
        mode_label=mode_label,
    )


def configure_environment(config: WorkflowCliConfig) -> dict[str, Path]:
    paths = {
        "dataset_root": config.dataset_root,
        "normalized_output_dir": config.output_base / "1_normalized",
        "reports_output_dir": config.output_base / "4_reports",
        "aspects_output_dir": config.output_base / "2_aspects",
        "indexes_output_dir": config.output_base / "3_indexes",
        "feedback_output_dir": config.output_base / "5_feedback",
        "replay_output_dir": config.output_base / "5_replay",
        "html_output_dir": config.output_base / "6_html",
        "qdrant_path": config.output_base / "3_indexes" / "qdrant_store",
    }

    os.environ["PROMPT_VARIANT"] = config.prompt_variant

    os.environ["DATASET_ROOT"] = str(paths["dataset_root"])
    os.environ["NORMALIZED_OUTPUT_DIR"] = str(paths["normalized_output_dir"])
    os.environ["REPORTS_OUTPUT_DIR"] = str(paths["reports_output_dir"])
    os.environ["ASPECTS_OUTPUT_DIR"] = str(paths["aspects_output_dir"])
    os.environ["INDEXES_OUTPUT_DIR"] = str(paths["indexes_output_dir"])
    os.environ["FEEDBACK_OUTPUT_DIR"] = str(paths["feedback_output_dir"])
    os.environ["REPLAY_OUTPUT_DIR"] = str(paths["replay_output_dir"])
    os.environ["HTML_OUTPUT_DIR"] = str(paths["html_output_dir"])
    os.environ["QDRANT_PATH"] = str(paths["qdrant_path"])
    return paths


def execute_workflow(args: argparse.Namespace) -> WorkflowExecutionSummary:
    config = build_cli_config(args)
    paths = configure_environment(config)

    from decathlon_voc_analyzer.app.core.config import get_settings
    from decathlon_voc_analyzer.stage4_generation.html_export_service import HtmlExportService
    from decathlon_voc_analyzer.workflows.single_product_workflow import get_single_product_workflow

    get_settings.cache_clear()
    workflow = get_single_product_workflow()
    result = workflow.invoke(
        {
            "category": args.category,
            "product_id": args.product_id,
            "max_reviews": args.max_reviews,
            "top_k_per_route": args.top_k_per_route,
            "questions_per_aspect": args.questions_per_aspect,
            "use_llm": not args.no_llm,
            "skip_normalize": args.skip_normalize,
            "skip_index": args.skip_index,
        },
        config={"configurable": {"thread_id": f"workflow:{'cn' if args.cn else 'default'}:{args.category}:{args.product_id}"}},
    )

    overview = result["overview"]
    normalization = result.get("normalization")
    index_result = result.get("index_result")
    analysis = result["analysis"]
    html_export_path = None
    if args.export_html:
        analysis_path = Path(str(analysis.artifact_path)) if analysis.artifact_path else None
        normalized_path = paths["normalized_output_dir"] / args.category / f"{args.product_id}.json"
        if analysis_path is not None and analysis_path.exists():
            analysis_payload = orjson.loads(analysis_path.read_bytes())
            normalized_payload = orjson.loads(normalized_path.read_bytes()) if normalized_path.exists() else None
            html_content = HtmlExportService().render(analysis_payload=analysis_payload, normalized_payload=normalized_payload)
            html_target_dir = paths["html_output_dir"] / args.category
            html_target_dir.mkdir(parents=True, exist_ok=True)
            html_output_path = html_target_dir / f"{args.product_id}.html"
            html_output_path.write_text(html_content, encoding="utf-8")
            html_export_path = str(html_output_path)

    return WorkflowExecutionSummary(
        mode_label=config.mode_label,
        dataset_root=str(paths["dataset_root"]),
        prompt_variant=config.prompt_variant,
        reports_output_dir=str(paths["reports_output_dir"]),
        category=args.category,
        product_id=args.product_id,
        max_reviews=args.max_reviews,
        overview={
            "category_count": overview.category_count,
            "total_products": overview.total_products,
            "total_reviews": overview.total_reviews,
        },
        normalization=(
            {
                "normalized_products": normalization.stats.normalized_products,
                "report_path": normalization.report_path,
            }
            if normalization is not None
            else None
        ),
        index_result=(
            {
                "backend": index_result.backend,
                "indexed_products": index_result.stats.indexed_products,
                "index_path": index_result.index_path,
            }
            if index_result is not None
            else None
        ),
        analysis={
            "analysis_mode": analysis.analysis_mode,
            "artifact_path": analysis.artifact_path,
            "strengths": len(analysis.report.strengths),
            "weaknesses": len(analysis.report.weaknesses),
            "warnings": list(analysis.warnings),
        },
        html_export_path=html_export_path,
    )


def _render_text_summary(summary: WorkflowExecutionSummary, quiet: bool) -> str:
    lines: list[str] = []
    if not quiet:
        lines.append(f"[1/4] 当前模式: {summary.mode_label}")
        lines.append(f"       dataset_root = {summary.dataset_root}")
        lines.append(f"       prompt_variant = {summary.prompt_variant}")
        lines.append(f"       reports_output_dir = {summary.reports_output_dir}")
        lines.append(
            f"[2/4] 数据集概览: categories={summary.overview['category_count']}, products={summary.overview['total_products']}, reviews={summary.overview['total_reviews']}"
        )
        if summary.max_reviews is not None:
            lines.append(f"       review_limit = {summary.max_reviews}")
        if summary.normalization is not None:
            lines.append(
                "[3/4] 标准化完成: "
                f"normalized_products={summary.normalization['normalized_products']}, "
                f"report_path={summary.normalization['report_path']}"
            )
        else:
            lines.append("[3/4] 已跳过标准化阶段")
        if summary.index_result is not None:
            lines.append(
                "[4/4] 索引构建完成: "
                f"backend={summary.index_result['backend']}, "
                f"indexed_products={summary.index_result['indexed_products']}, "
                f"index_path={summary.index_result['index_path']}"
            )
        else:
            lines.append("[4/4] 已跳过索引阶段")

    lines.append("[完成] 分析已生成")
    lines.append(f"       analysis_mode = {summary.analysis['analysis_mode']}")
    lines.append(f"       artifact_path = {summary.analysis['artifact_path']}")
    lines.append(f"       strengths = {summary.analysis['strengths']}")
    lines.append(f"       weaknesses = {summary.analysis['weaknesses']}")
    if summary.html_export_path:
        lines.append(f"       html_export_path = {summary.html_export_path}")
    warnings = summary.analysis["warnings"]
    if warnings:
        lines.append("       warnings:")
        for warning in warnings[:10]:
            lines.append(f"       - {warning}")
    return "\n".join(lines)


def _render_json_summary(summary: WorkflowExecutionSummary) -> bytes:
    return orjson.dumps(
        {
            "mode_label": summary.mode_label,
            "dataset_root": summary.dataset_root,
            "prompt_variant": summary.prompt_variant,
            "reports_output_dir": summary.reports_output_dir,
            "category": summary.category,
            "product_id": summary.product_id,
            "max_reviews": summary.max_reviews,
            "overview": summary.overview,
            "normalization": summary.normalization,
            "index_result": summary.index_result,
            "analysis": summary.analysis,
            "html_export_path": summary.html_export_path,
        },
        option=orjson.OPT_INDENT_2,
    )


def main() -> None:
    args = parse_args()
    summary = execute_workflow(args)
    if args.output_format == "json":
        sys.stdout.buffer.write(_render_json_summary(summary))
        sys.stdout.write("\n")
        return
    print(_render_text_summary(summary, quiet=args.quiet))


if __name__ == "__main__":
    main()