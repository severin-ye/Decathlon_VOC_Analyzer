import importlib.util
from argparse import Namespace
from pathlib import Path

import orjson


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT_DIR / "04_scripts" / "run_workflow.py"


def _load_run_workflow_module():
    spec = importlib.util.spec_from_file_location("run_workflow_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_preprocess_review_flag_alias() -> None:
    module = _load_run_workflow_module()

    assert module._preprocess_argv(["--category", "backpack", "--R_5", "--no-llm"]) == [
        "--category",
        "backpack",
        "--max-reviews",
        "5",
        "--no-llm",
    ]


def test_build_cli_config_for_cn_namespace() -> None:
    module = _load_run_workflow_module()

    args = Namespace(
        cn=True,
        dataset_root=None,
        prompt_variant=None,
        output_namespace=None,
    )

    config = module.build_cli_config(args)

    assert config.prompt_variant == "CN"
    assert config.mode_label == "中文数据集"
    assert str(config.dataset_root).endswith("01_data/02_audit_zh_products/products")
    assert str(config.output_base).endswith("02_outputs/CN")


def test_render_text_summary_quiet_mode() -> None:
    module = _load_run_workflow_module()

    summary = module.WorkflowExecutionSummary(
        mode_label="主项目原始数据集",
        dataset_root="/tmp/dataset",
        prompt_variant="main",
        reports_output_dir="/tmp/reports",
        category="backpack",
        product_id="backpack_010",
        max_reviews=5,
        overview={"category_count": 3, "total_products": 192, "total_reviews": 33697},
        normalization={"normalized_products": 1, "report_path": "/tmp/report.json"},
        index_result={"backend": "local", "indexed_products": 1, "index_path": "/tmp/index.json"},
        analysis={
            "analysis_mode": "heuristic",
            "artifact_path": "/tmp/analysis.json",
            "strengths": 3,
            "weaknesses": 0,
            "warnings": [],
        },
        html_export_path="/tmp/report.html",
    )

    text = module._render_text_summary(summary, quiet=True)

    assert "[完成] 分析已生成" in text
    assert "[1/4]" not in text
    assert "analysis_mode = heuristic" in text
    assert "html_export_path = /tmp/report.html" in text


def test_render_json_summary_contains_batch_fields() -> None:
    module = _load_run_workflow_module()

    summary = module.WorkflowExecutionSummary(
        mode_label="主项目原始数据集",
        dataset_root="/tmp/dataset",
        prompt_variant="main",
        reports_output_dir="/tmp/reports",
        category="backpack",
        product_id="backpack_010",
        max_reviews=5,
        overview={"category_count": 3, "total_products": 192, "total_reviews": 33697},
        normalization=None,
        index_result=None,
        analysis={
            "analysis_mode": "heuristic",
            "artifact_path": "/tmp/analysis.json",
            "strengths": 3,
            "weaknesses": 0,
            "warnings": [],
        },
        html_export_path="/tmp/report.html",
    )

    payload = orjson.loads(module._render_json_summary(summary))

    assert payload["prompt_variant"] == "main"
    assert payload["overview"]["total_reviews"] == 33697
    assert payload["analysis"]["artifact_path"] == "/tmp/analysis.json"
    assert payload["html_export_path"] == "/tmp/report.html"