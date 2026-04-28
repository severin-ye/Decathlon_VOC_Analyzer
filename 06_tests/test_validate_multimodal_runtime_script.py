import importlib.util
from argparse import Namespace
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT_DIR / "04_scripts" / "validate_multimodal_runtime.py"


def _load_validate_module():
    spec = importlib.util.spec_from_file_location("validate_multimodal_runtime_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_prepare_workflow_args_preserves_manifest_and_html_flags() -> None:
    module = _load_validate_module()

    args = Namespace(
        cn=False,
        category="sunglasses",
        product_id="sunglasses_010",
        dataset_root=None,
        prompt_variant=None,
        output_namespace=None,
        retrieval_backend="qdrant",
        qdrant_path=None,
        qdrant_scope="isolated",
        max_reviews=2,
        top_k_per_route=2,
        questions_per_aspect=2,
        skip_normalize=False,
        skip_index=False,
        export_html=True,
        write_manifest=True,
        manifest_path="02_outputs/7_manifests/sunglasses/sunglasses_010_run_manifest.json",
        allow_heuristic=False,
    )

    workflow_args = module._prepare_workflow_args(args)

    assert workflow_args.export_html is True
    assert workflow_args.write_manifest is True
    assert workflow_args.manifest_path == "02_outputs/7_manifests/sunglasses/sunglasses_010_run_manifest.json"
    assert workflow_args.output_format == "json"
    assert workflow_args.quiet is True
    assert workflow_args.no_llm is False


def test_materialize_summary_writes_manifest_after_workflow() -> None:
    module = _load_validate_module()

    calls: list[str] = []
    summary = object()

    class RunWorkflowStub:
        @staticmethod
        def execute_workflow(args, paths):
            calls.append("execute")
            assert args.write_manifest is True
            return summary

        @staticmethod
        def maybe_write_manifest(args, current_summary, paths):
            calls.append("manifest")
            assert args.write_manifest is True
            assert current_summary is summary
            return "materialized-summary"

    workflow_args = Namespace(write_manifest=True)
    paths = {"manifests_output_dir": ROOT_DIR / "02_outputs" / "7_manifests"}

    result = module._materialize_summary(RunWorkflowStub(), workflow_args, paths)

    assert result == "materialized-summary"
    assert calls == ["execute", "manifest"]