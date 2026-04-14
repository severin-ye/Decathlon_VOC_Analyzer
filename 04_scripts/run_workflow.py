import argparse
import os
import sys
import re
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "05_src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


REVIEW_FLAG_PATTERN = re.compile(r"^--R_(\d+)$")


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
    parser.add_argument("--cn", action="store_true", help="切换到中文测试数据集与中文输出目录")
    parser.add_argument("--category", default="backpack", help="类目，例如 backpack")
    parser.add_argument("--product-id", default="backpack_010", help="商品 ID，例如 backpack_010")
    parser.add_argument("--max-reviews", type=int, default=None, help="限制参与分析的评论数量")
    parser.add_argument("--top-k-per-route", type=int, default=2, help="每个模态召回的证据数量")
    parser.add_argument("--questions-per-aspect", type=int, default=2, help="每个 aspect 生成的问题数量")
    parser.add_argument("--no-llm", action="store_true", help="禁用 LLM，使用本地启发式链路")
    parser.add_argument("--skip-normalize", action="store_true", help="跳过标准化落盘阶段")
    parser.add_argument("--skip-index", action="store_true", help="跳过索引构建阶段")
    parser.epilog = "支持简写参数，例如: --R_5 表示只分析前 5 条评论"
    return parser.parse_args(_preprocess_argv(sys.argv[1:]))


def configure_environment(use_cn_dataset: bool) -> dict[str, Path]:
    if use_cn_dataset:
        paths = {
            "dataset_root": ROOT_DIR / "01_data" / "02_audit_zh_products" / "products",
            "normalized_output_dir": ROOT_DIR / "02_outputs" / "CN" / "1_normalized",
            "reports_output_dir": ROOT_DIR / "02_outputs" / "CN" / "4_reports",
            "aspects_output_dir": ROOT_DIR / "02_outputs" / "CN" / "2_aspects",
            "indexes_output_dir": ROOT_DIR / "02_outputs" / "CN" / "3_indexes",
            "qdrant_path": ROOT_DIR / "02_outputs" / "CN" / "3_indexes" / "qdrant_store",
        }
        os.environ["PROMPT_VARIANT"] = "CN"
    else:
        paths = {
            "dataset_root": ROOT_DIR / "01_data" / "01_raw_products" / "products",
            "normalized_output_dir": ROOT_DIR / "02_outputs" / "1_normalized",
            "reports_output_dir": ROOT_DIR / "02_outputs" / "4_reports",
            "aspects_output_dir": ROOT_DIR / "02_outputs" / "2_aspects",
            "indexes_output_dir": ROOT_DIR / "02_outputs" / "3_indexes",
            "qdrant_path": ROOT_DIR / "02_outputs" / "3_indexes" / "qdrant_store",
        }
        os.environ["PROMPT_VARIANT"] = "main"

    os.environ["DATASET_ROOT"] = str(paths["dataset_root"])
    os.environ["NORMALIZED_OUTPUT_DIR"] = str(paths["normalized_output_dir"])
    os.environ["REPORTS_OUTPUT_DIR"] = str(paths["reports_output_dir"])
    os.environ["ASPECTS_OUTPUT_DIR"] = str(paths["aspects_output_dir"])
    os.environ["INDEXES_OUTPUT_DIR"] = str(paths["indexes_output_dir"])
    os.environ["QDRANT_PATH"] = str(paths["qdrant_path"])
    return paths


def main() -> None:
    args = parse_args()
    paths = configure_environment(use_cn_dataset=args.cn)

    from decathlon_voc_analyzer.app.core.config import get_settings
    from decathlon_voc_analyzer.workflows.single_product_workflow import get_single_product_workflow

    get_settings.cache_clear()
    workflow = get_single_product_workflow()

    mode_label = "中文测试数据集" if args.cn else "主项目原始数据集"
    print(f"[1/4] 当前模式: {mode_label}")
    print(f"       dataset_root = {paths['dataset_root']}")
    print(f"       reports_output_dir = {paths['reports_output_dir']}")

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
    print(f"[2/4] 数据集概览: categories={overview.category_count}, products={overview.total_products}, reviews={overview.total_reviews}")
    if args.max_reviews is not None:
        print(f"       review_limit = {args.max_reviews}")

    normalization = result.get("normalization")
    if normalization is not None:
        print(
            "[3/4] 标准化完成: "
            f"normalized_products={normalization.stats.normalized_products}, "
            f"report_path={normalization.report_path}"
        )
    else:
        print("[3/4] 已跳过标准化阶段")

    index_result = result.get("index_result")
    if index_result is not None:
        print(
            "[4/4] 索引构建完成: "
            f"backend={index_result.backend}, "
            f"indexed_products={index_result.stats.indexed_products}, "
            f"index_path={index_result.index_path}"
        )
    else:
        print("[4/4] 已跳过索引阶段")

    analysis = result["analysis"]

    print("[完成] 分析已生成")
    print(f"       analysis_mode = {analysis.analysis_mode}")
    print(f"       artifact_path = {analysis.artifact_path}")
    print(f"       strengths = {len(analysis.report.strengths)}")
    print(f"       weaknesses = {len(analysis.report.weaknesses)}")
    if analysis.warnings:
        print("       warnings:")
        for warning in analysis.warnings[:10]:
            print(f"       - {warning}")


if __name__ == "__main__":
    main()