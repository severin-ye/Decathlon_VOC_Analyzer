from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_serve_ui_module():
    module_path = Path(__file__).resolve().parents[1] / "04_scripts" / "experiment_ui" / "serve_ui.py"
    spec = importlib.util.spec_from_file_location("experiment_ui_serve_ui", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_experiment_results_route_ignores_cache_busting_query() -> None:
    module = _load_serve_ui_module()
    handler = object.__new__(module.Handler)

    translated = Path(handler.translate_path("/experiment_results/experiment_summary.json?t=123"))

    assert translated == module.EXPERIMENT_RESULTS_DIR / "experiment_summary.json"
