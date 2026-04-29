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


def test_parse_args_accepts_resume_from_aspects(monkeypatch) -> None:
    module = _load_run_workflow_module()

    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "run_workflow.py",
            "--category",
            "backpack",
            "--product-id",
            "backpack_010",
            "--resume-from-aspects",
        ],
    )

    args = module.parse_args()

    assert args.resume_from_aspects is True


def test_parse_args_accepts_resume_from_analysis_checkpoint(monkeypatch) -> None:
    module = _load_run_workflow_module()

    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "run_workflow.py",
            "--category",
            "backpack",
            "--product-id",
            "backpack_010",
            "--resume-from-analysis-checkpoint",
        ],
    )

    args = module.parse_args()

    assert args.resume_from_analysis_checkpoint is True


def test_build_cli_config_for_cn_namespace() -> None:
    module = _load_run_workflow_module()

    args = Namespace(
        cn=True,
        dataset_root=None,
        prompt_variant=None,
        output_namespace=None,
        retrieval_backend="qdrant",
        qdrant_path=None,
        qdrant_scope="isolated",
        category="backpack",
        product_id="backpack_010",
    )

    config = module.build_cli_config(args)

    assert config.prompt_variant == "CN"
    assert config.mode_label == "中文数据集"
    assert config.retrieval_backend == "qdrant"
    assert str(config.dataset_root).endswith("01_data/02_audit_zh_products/products")
    assert str(config.output_base).endswith("02_outputs/CN")
    assert "qdrant_runs/backpack/backpack_010/run_" in str(config.qdrant_path)


def test_build_cli_config_can_use_shared_qdrant_path() -> None:
    module = _load_run_workflow_module()

    args = Namespace(
        cn=False,
        dataset_root=None,
        prompt_variant=None,
        output_namespace=None,
        retrieval_backend="qdrant",
        qdrant_path=None,
        qdrant_scope="shared",
        category="backpack",
        product_id="backpack_010",
    )

    config = module.build_cli_config(args)

    assert str(config.qdrant_path).endswith("02_outputs/3_indexes/qdrant_store")


def test_build_cli_config_normalizes_prompt_variant_alias() -> None:
    module = _load_run_workflow_module()

    args = Namespace(
        cn=False,
        dataset_root=None,
        prompt_variant="zh-cn",
        output_namespace=None,
        retrieval_backend="qdrant",
        qdrant_path=None,
        qdrant_scope="isolated",
        category="backpack",
        product_id="backpack_010",
    )

    config = module.build_cli_config(args)

    assert config.prompt_variant == "CN"
    assert config.mode_label == "中文数据集"


def test_thread_scope_label_uses_normalized_prompt_variant() -> None:
    module = _load_run_workflow_module()

    args = Namespace(cn=False)

    assert module._thread_scope_label(args, "CN") == "cn"
    assert module._thread_scope_label(args, "main") == "default"


def test_configure_environment_defaults_batch_runs_to_qdrant(tmp_path, monkeypatch) -> None:
    module = _load_run_workflow_module()
    monkeypatch.setattr(module.os, "environ", dict(module.os.environ))

    config = module.WorkflowCliConfig(
        dataset_root=tmp_path / "dataset",
        output_base=tmp_path / "outputs",
        prompt_variant="main",
        mode_label="主项目原始数据集",
        retrieval_backend="qdrant",
        qdrant_path=tmp_path / "outputs" / "3_indexes" / "qdrant_store",
    )

    module.configure_environment(config)

    assert module.os.environ["RETRIEVAL_BACKEND"] == "qdrant"


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
        review_sampling={
            "profile_name": "problem_first",
            "requested_reviews": 5,
            "selected_reviews": 5,
            "allocations": [{"rating": 1, "selected_count": 2}],
        },
        retrieval_runtime={
            "native_multimodal_enabled": True,
            "image_embedding_backend": "clip",
            "multimodal_reranker_backend": "qwen_vl",
        },
        analysis={
            "analysis_mode": "heuristic",
            "artifact_path": "/tmp/analysis.json",
            "strengths": 3,
            "weaknesses": 0,
            "replay_applied": True,
            "replay_persistent_issue_count": 2,
            "replay_resolved_issue_count": 1,
            "warnings": [],
        },
        artifact_bundle={
            "analysis_path": "/tmp/analysis.json",
            "feedback_path": "/tmp/feedback.json",
            "replay_path": "/tmp/replay.json",
        },
        html_export_path="/tmp/report.html",
        manifest_path="/tmp/run_manifest.json",
    )

    text = module._render_text_summary(summary, quiet=True)

    assert "[完成] 分析已生成" in text
    assert "[1/4]" not in text
    assert "analysis_mode = heuristic" in text
    assert "native_multimodal_enabled = True" in text
    assert "image_embedding_backend = clip" in text
    assert "multimodal_reranker_backend = qwen_vl" in text
    assert "feedback_path = /tmp/feedback.json" in text
    assert "replay_path = /tmp/replay.json" in text
    assert "html_export_path = /tmp/report.html" in text
    assert "manifest_path = /tmp/run_manifest.json" in text


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
        review_sampling={
            "profile_name": "problem_first",
            "requested_reviews": 5,
            "selected_reviews": 5,
            "allocations": [{"rating": 1, "selected_count": 2}],
        },
        retrieval_runtime={
            "native_multimodal_enabled": True,
            "image_embedding_backend": "clip",
            "multimodal_reranker_backend": "qwen_vl",
        },
        analysis={
            "analysis_mode": "heuristic",
            "artifact_path": "/tmp/analysis.json",
            "strengths": 3,
            "weaknesses": 0,
            "replay_applied": True,
            "replay_persistent_issue_count": 2,
            "replay_resolved_issue_count": 1,
            "warnings": [],
        },
        artifact_bundle={
            "analysis_path": "/tmp/analysis.json",
            "feedback_path": "/tmp/feedback.json",
            "replay_path": "/tmp/replay.json",
        },
        html_export_path="/tmp/report.html",
        manifest_path="/tmp/run_manifest.json",
    )

    payload = orjson.loads(module._render_json_summary(summary))

    assert payload["prompt_variant"] == "main"
    assert payload["overview"]["total_reviews"] == 33697
    assert payload["review_sampling"]["profile_name"] == "problem_first"
    assert payload["retrieval_runtime"]["native_multimodal_enabled"] is True
    assert payload["retrieval_runtime"]["image_embedding_backend"] == "clip"
    assert payload["analysis"]["artifact_path"] == "/tmp/analysis.json"
    assert payload["analysis"]["replay_applied"] is True
    assert payload["artifact_bundle"]["feedback_path"] == "/tmp/feedback.json"
    assert payload["html_export_path"] == "/tmp/report.html"
    assert payload["manifest_path"] == "/tmp/run_manifest.json"