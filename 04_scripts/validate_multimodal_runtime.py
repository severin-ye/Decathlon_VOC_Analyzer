import argparse
import importlib.util
import sys
from pathlib import Path

import orjson


ROOT_DIR = Path(__file__).resolve().parents[1]
RUN_WORKFLOW_PATH = ROOT_DIR / "04_scripts" / "run_workflow.py"


def _load_run_workflow_module():
    spec = importlib.util.spec_from_file_location("run_workflow_script", RUN_WORKFLOW_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="验证真实工作流是否走到 LLM + 原生多模态主链路")
    parser.add_argument("--cn", action="store_true", help="使用中文数据集模式")
    parser.add_argument("--category", default="backpack", help="类目，例如 backpack")
    parser.add_argument("--product-id", default="backpack_010", help="商品 ID，例如 backpack_010")
    parser.add_argument("--dataset-root", default=None, help="可选，显式指定数据集根目录")
    parser.add_argument("--prompt-variant", default=None, help="可选，显式指定提示词变体")
    parser.add_argument("--output-namespace", default=None, help="可选，显式指定输出命名空间")
    parser.add_argument("--retrieval-backend", choices=["qdrant", "local"], default="qdrant", help="默认沿用批跑入口的 qdrant")
    parser.add_argument("--qdrant-path", default=None, help="可选，显式指定 Qdrant 存储目录")
    parser.add_argument("--qdrant-scope", choices=["isolated", "shared"], default="isolated", help="默认每次验证使用独立 Qdrant 目录")
    parser.add_argument("--max-reviews", type=int, default=2, help="验证时抽取的评论上限")
    parser.add_argument("--top-k-per-route", type=int, default=2, help="每个 route 召回条数")
    parser.add_argument("--questions-per-aspect", type=int, default=2, help="每个 aspect 问题数")
    parser.add_argument("--skip-normalize", action="store_true", help="跳过标准化")
    parser.add_argument("--skip-index", action="store_true", help="跳过索引构建")
    parser.add_argument("--allow-heuristic", action="store_true", help="允许回退到 heuristic；默认要求 llm")
    return parser.parse_args()


def _validate_summary(summary, allow_heuristic: bool) -> dict[str, object]:
    retrieval_runtime = summary.retrieval_runtime or {}
    failures: list[str] = []

    if not allow_heuristic and summary.analysis["analysis_mode"] != "llm":
        failures.append(f"analysis_mode={summary.analysis['analysis_mode']}")
    if retrieval_runtime.get("native_multimodal_enabled") is not True:
        failures.append("native_multimodal_enabled=false")
    if retrieval_runtime.get("image_embedding_backend") != "clip":
        failures.append(f"image_embedding_backend={retrieval_runtime.get('image_embedding_backend')}")
    if retrieval_runtime.get("multimodal_reranker_backend") != "qwen_vl":
        failures.append(f"multimodal_reranker_backend={retrieval_runtime.get('multimodal_reranker_backend')}")

    return {
        "passed": not failures,
        "failures": failures,
        "analysis_mode": summary.analysis["analysis_mode"],
        "retrieval_runtime": retrieval_runtime,
        "artifact_path": summary.analysis["artifact_path"],
        "index_result": summary.index_result,
    }


def _prepare_workflow_args(args: argparse.Namespace) -> argparse.Namespace:
    payload = vars(args).copy()
    payload.setdefault("no_llm", False)
    payload.setdefault("export_html", False)
    payload.setdefault("write_manifest", False)
    payload.setdefault("manifest_path", None)
    payload.setdefault("output_format", "json")
    payload.setdefault("quiet", True)
    return argparse.Namespace(**payload)


def main() -> None:
    run_workflow = _load_run_workflow_module()
    from decathlon_voc_analyzer.stage3_retrieval.index_backends import dispose_index_backend

    args = parse_args()
    paths = None
    try:
        workflow_args = _prepare_workflow_args(args)
        config = run_workflow.build_cli_config(workflow_args)
        paths = run_workflow.configure_environment(config)
        summary = run_workflow.execute_workflow(workflow_args, paths)
        validation = _validate_summary(summary, allow_heuristic=args.allow_heuristic)
        payload = {
            "validation": validation,
            "summary": run_workflow._summary_payload(summary),
        }
        sys.stdout.buffer.write(orjson.dumps(payload, option=orjson.OPT_INDENT_2))
        sys.stdout.write("\n")
        if not validation["passed"]:
            raise SystemExit(1)
    finally:
        dispose_index_backend()


if __name__ == "__main__":
    main()