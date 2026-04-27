#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import orjson


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "05_src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from decathlon_voc_analyzer.evaluation import ManifestEvaluationService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="基于 manifest + artifact + sidecar 生成分层评估报告")
    parser.add_argument(
        "--manifest-root",
        default="02_outputs/7_manifests",
        help="manifest 根目录或单个 manifest 文件路径",
    )
    parser.add_argument(
        "--output",
        default="02_outputs/8_evaluations/manifest_evaluation_report.json",
        help="评估报告输出路径",
    )
    return parser.parse_args()


def _resolve_path(raw_path: str) -> Path:
    candidate = Path(raw_path)
    return candidate if candidate.is_absolute() else (ROOT_DIR / candidate).resolve()


def main() -> None:
    args = parse_args()
    manifest_root = _resolve_path(args.manifest_root)
    output_path = _resolve_path(args.output)

    service = ManifestEvaluationService()
    report = service.build_report(manifest_root)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(orjson.dumps(report, option=orjson.OPT_INDENT_2))

    print(f"manifest_root = {manifest_root}")
    print(f"run_count = {report['run_count']}")
    print(f"output_path = {output_path}")


if __name__ == "__main__":
    main()