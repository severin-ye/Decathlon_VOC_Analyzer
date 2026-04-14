import argparse
import sys
from pathlib import Path

import orjson


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "05_src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导出单商品 HTML 分析报告")
    parser.add_argument("--category", required=True, help="类目，例如 backpack")
    parser.add_argument("--product-id", required=True, help="商品 ID，例如 backpack_010")
    parser.add_argument("--analysis-path", default=None, help="可选，直接指定 analysis json 路径")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    from decathlon_voc_analyzer.app.core.config import get_settings
    from decathlon_voc_analyzer.stage4_generation.html_export_service import HtmlExportService

    settings = get_settings()
    analysis_path = Path(args.analysis_path) if args.analysis_path else settings.reports_output_dir / args.category / f"{args.product_id}_analysis.json"
    normalized_path = settings.normalized_output_dir / args.category / f"{args.product_id}.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"analysis artifact not found: {analysis_path}")

    analysis_payload = orjson.loads(analysis_path.read_bytes())
    normalized_payload = orjson.loads(normalized_path.read_bytes()) if normalized_path.exists() else None

    html_content = HtmlExportService().render(analysis_payload=analysis_payload, normalized_payload=normalized_payload)
    target_dir = settings.html_output_dir / args.category
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / f"{args.product_id}.html"
    output_path.write_text(html_content, encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()