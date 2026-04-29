import argparse
import os
import sys
import re
from datetime import datetime, timezone
from dataclasses import dataclass, replace
from pathlib import Path

import orjson


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "05_src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from decathlon_voc_analyzer.runtime_progress import WorkflowProgressReporter, use_workflow_progress


REVIEW_FLAG_PATTERN = re.compile(r"^--R_(\d+)$")


@dataclass(frozen=True)
class WorkflowCliConfig:
    dataset_root: Path
    output_base: Path
    prompt_variant: str
    mode_label: str
    retrieval_backend: str
    qdrant_path: Path


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
    review_sampling: dict[str, object] | None
    retrieval_runtime: dict[str, object] | None
    analysis: dict[str, object]
    artifact_bundle: dict[str, str | None] | None
    html_export_path: str | None
    manifest_path: str | None


WORKFLOW_PROGRESS_PLAN = [
    ("overview", "数据集概览", [("scan", "扫描类目与商品"), ("summarize", "汇总概览")]),
    ("normalize", "标准化数据", [("select", "选择目标商品"), ("normalize_products", "逐个标准化商品"), ("persist", "落盘标准化产物")]),
    ("index", "构建索引", [("load_packages", "加载商品包"), ("embed_text", "生成文本向量"), ("embed_image", "生成图像向量"), ("persist", "保存索引快照")]),
    ("analyze", "生成分析", [("extract", "抽取评论"), ("questions", "规划和生成问题"), ("retrieve", "检索证据"), ("quality", "评估检索质量"), ("report", "生成报告"), ("attribution", "归因和修订"), ("persist", "写入分析产物")]),
    ("export_html", "导出 HTML", [("render", "渲染 HTML"), ("write", "写入 HTML 文件")]),
    ("write_manifest", "写入 Manifest", [("serialize", "序列化摘要"), ("write", "写入 Manifest 文件")]),
]


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
    parser.add_argument("--retrieval-backend", choices=["qdrant", "local"], default="qdrant", help="批跑默认使用 qdrant；如需回退可显式指定 local")
    parser.add_argument("--qdrant-path", default=None, help="可选，显式指定 Qdrant 存储目录；未指定时按 qdrant-scope 自动生成")
    parser.add_argument(
        "--qdrant-scope",
        choices=["isolated", "shared"],
        default="isolated",
        help="Qdrant 目录作用域；isolated 为每次运行单独目录，shared 复用固定 qdrant_store",
    )
    parser.add_argument("--max-reviews", type=int, default=None, help="限制参与分析的评论数量")
    parser.add_argument("--top-k-per-route", type=int, default=2, help="每个模态召回的证据数量")
    parser.add_argument("--questions-per-aspect", type=int, default=2, help="每个 aspect 生成的问题数量")
    parser.add_argument("--no-llm", action="store_true", help="禁用 LLM，使用本地启发式链路")
    parser.add_argument("--skip-normalize", action="store_true", help="跳过标准化落盘阶段")
    parser.add_argument("--skip-index", action="store_true", help="跳过索引构建阶段")
    parser.add_argument("--export-html", action="store_true", help="分析完成后顺带导出单商品 HTML 页面")
    parser.add_argument("--write-manifest", action="store_true", help="将本次运行摘要落盘为 manifest json")
    parser.add_argument("--manifest-path", default=None, help="可选，显式指定 manifest 输出路径")
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


def _mode_label_for_variant(prompt_variant: str) -> str:
    return "中文数据集" if prompt_variant == "CN" else "主项目原始数据集"


def _thread_scope_label(args: argparse.Namespace, prompt_variant: str) -> str:
    return "cn" if prompt_variant == "CN" else "default"


def _build_run_stamp() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    return f"run_{timestamp}_pid{os.getpid()}"


def _resolve_qdrant_path(args: argparse.Namespace, output_base: Path) -> Path:
    if args.qdrant_path:
        candidate = Path(args.qdrant_path)
        return candidate if candidate.is_absolute() else (ROOT_DIR / candidate)
    shared_path = output_base / "3_indexes" / "qdrant_store"
    if args.qdrant_scope == "shared":
        return shared_path
    return output_base / "3_indexes" / "qdrant_runs" / args.category / args.product_id / _build_run_stamp()


def build_cli_config(args: argparse.Namespace) -> WorkflowCliConfig:
    dataset_root = _resolve_dataset_root(args)
    output_base = _resolve_output_base(args)
    prompt_variant = _resolve_prompt_variant(args)
    mode_label = _mode_label_for_variant(prompt_variant)
    qdrant_path = _resolve_qdrant_path(args, output_base)
    return WorkflowCliConfig(
        dataset_root=dataset_root,
        output_base=output_base,
        prompt_variant=prompt_variant,
        mode_label=mode_label,
        retrieval_backend=args.retrieval_backend,
        qdrant_path=qdrant_path,
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
        "manifests_output_dir": config.output_base / "7_manifests",
        "qdrant_path": config.qdrant_path,
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
    os.environ["RETRIEVAL_BACKEND"] = config.retrieval_backend
    return paths


def _resolve_manifest_path(args: argparse.Namespace, paths: dict[str, Path]) -> Path:
    if args.manifest_path:
        candidate = Path(args.manifest_path)
        return candidate if candidate.is_absolute() else (ROOT_DIR / candidate)
    return paths["manifests_output_dir"] / args.category / f"{args.product_id}_run_manifest.json"


def execute_workflow(args: argparse.Namespace, paths: dict[str, Path], progress: WorkflowProgressReporter | None = None) -> WorkflowExecutionSummary:
    from decathlon_voc_analyzer.app.core.config import get_settings
    from decathlon_voc_analyzer.app.core.runtime_policy import validate_full_power_prerequisites

    get_settings.cache_clear()
    settings = get_settings()
    validate_full_power_prerequisites(
        use_llm=not args.no_llm,
        retrieval_backend=str(os.environ.get("RETRIEVAL_BACKEND") or settings.retrieval_backend),
        settings=settings,
    )

    from decathlon_voc_analyzer.stage4_generation.html_export_service import HtmlExportService
    from decathlon_voc_analyzer.workflows.single_product_workflow import get_single_product_workflow

    workflow = get_single_product_workflow()
    if progress is not None:
        progress.note("工作流已启动，正在按顺序执行各模块。")
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
        config={"configurable": {"thread_id": f"workflow:{_thread_scope_label(args, str(os.environ.get('PROMPT_VARIANT') or 'main'))}:{args.category}:{args.product_id}"}},
    )

    overview = result["overview"]
    normalization = result.get("normalization")
    index_result = result.get("index_result")
    analysis = result["analysis"]
    sampling_plan = analysis.extraction.sampling_plan
    retrieval_runtime = analysis.retrieval_runtime.model_dump(mode="json") if analysis.retrieval_runtime is not None else None
    html_export_path = None
    if args.export_html:
        if progress is not None:
            progress.activate_module("export_html", detail="准备导出单商品 HTML 页面")
            progress.activate_step("export_html", "render", detail="读取分析结果并生成 HTML 内容")
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
        if progress is not None:
            progress.complete_step("export_html", "render")
            progress.activate_step("export_html", "write", detail=f"{html_export_path or 'no output written'}")
            progress.complete_step("export_html", "write")
            progress.complete_module("export_html")

    return WorkflowExecutionSummary(
        mode_label=_mode_label_for_variant(str(os.environ.get("PROMPT_VARIANT") or "main")),
        dataset_root=str(paths["dataset_root"]),
        prompt_variant=str(os.environ.get("PROMPT_VARIANT") or "main"),
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
        review_sampling=(sampling_plan.model_dump(mode="json") if sampling_plan is not None else None),
        retrieval_runtime=retrieval_runtime,
        analysis={
            "analysis_mode": analysis.analysis_mode,
            "artifact_path": analysis.artifact_path,
            "strengths": len(analysis.report.strengths),
            "weaknesses": len(analysis.report.weaknesses),
            "replay_applied": bool(analysis.replay_summary and analysis.replay_summary.applied),
            "replay_persistent_issue_count": len(analysis.replay_summary.persistent_issue_labels) if analysis.replay_summary else 0,
            "replay_resolved_issue_count": len(analysis.replay_summary.resolved_issue_labels) if analysis.replay_summary else 0,
            "warnings": list(analysis.warnings),
        },
        artifact_bundle=(analysis.artifact_bundle.model_dump(mode="json") if analysis.artifact_bundle is not None else None),
        html_export_path=html_export_path,
        manifest_path=None,
    )


def _summary_payload(summary: WorkflowExecutionSummary) -> dict[str, object]:
    return {
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
        "review_sampling": summary.review_sampling,
        "retrieval_runtime": summary.retrieval_runtime,
        "analysis": summary.analysis,
        "artifact_bundle": summary.artifact_bundle,
        "html_export_path": summary.html_export_path,
        "manifest_path": summary.manifest_path,
    }


def maybe_write_manifest(args: argparse.Namespace, summary: WorkflowExecutionSummary, paths: dict[str, Path], progress: WorkflowProgressReporter | None = None) -> WorkflowExecutionSummary:
    if not args.write_manifest and not args.manifest_path:
        return summary
    manifest_path = _resolve_manifest_path(args, paths)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    if progress is not None:
        progress.activate_module("write_manifest", detail="准备写入本次运行摘要")
        progress.activate_step("write_manifest", "serialize", detail="整理摘要 JSON")
    materialized_summary = replace(summary, manifest_path=str(manifest_path))
    manifest_path.write_bytes(orjson.dumps(_summary_payload(materialized_summary), option=orjson.OPT_INDENT_2))
    if progress is not None:
        progress.complete_step("write_manifest", "serialize")
        progress.activate_step("write_manifest", "write", detail=str(manifest_path))
        progress.complete_step("write_manifest", "write")
        progress.complete_module("write_manifest")
    return materialized_summary


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
    if summary.retrieval_runtime is not None:
        lines.append(f"       native_multimodal_enabled = {summary.retrieval_runtime.get('native_multimodal_enabled')}")
        lines.append(f"       image_embedding_backend = {summary.retrieval_runtime.get('image_embedding_backend')}")
        lines.append(f"       multimodal_reranker_backend = {summary.retrieval_runtime.get('multimodal_reranker_backend')}")
    if summary.artifact_bundle is not None:
        lines.append(f"       feedback_path = {summary.artifact_bundle.get('feedback_path')}")
        lines.append(f"       replay_path = {summary.artifact_bundle.get('replay_path')}")
    if summary.html_export_path:
        lines.append(f"       html_export_path = {summary.html_export_path}")
    if summary.manifest_path:
        lines.append(f"       manifest_path = {summary.manifest_path}")
    warnings = summary.analysis["warnings"]
    if warnings:
        lines.append("       warnings:")
        for warning in warnings[:10]:
            lines.append(f"       - {warning}")
    return "\n".join(lines)


def _render_json_summary(summary: WorkflowExecutionSummary) -> bytes:
    return orjson.dumps(_summary_payload(summary), option=orjson.OPT_INDENT_2)


def main() -> None:
    from decathlon_voc_analyzer.stage3_retrieval.index_backends import dispose_index_backend
    from decathlon_voc_analyzer.app.core.runtime_policy import RuntimePolicyError

    args = parse_args()
    config = build_cli_config(args)
    paths = configure_environment(config)
    progress = WorkflowProgressReporter(WORKFLOW_PROGRESS_PLAN, enabled=not args.quiet)
    try:
        try:
            with progress:
                with use_workflow_progress(progress):
                    progress.note("工作流已启动，正在按顺序执行各模块。")
                    summary = execute_workflow(args, paths, progress=progress)
                    summary = maybe_write_manifest(args, summary, paths, progress=progress)
                    if args.output_format == "json":
                        sys.stdout.buffer.write(_render_json_summary(summary))
                        sys.stdout.write("\n")
                        return
                    print(_render_text_summary(summary, quiet=args.quiet))
        except RuntimePolicyError as exc:
            print(exc.render(), file=sys.stderr)
            raise SystemExit(1) from exc
    finally:
        dispose_index_backend()


if __name__ == "__main__":
    main()