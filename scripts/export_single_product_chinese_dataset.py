import argparse
import json
from pathlib import Path

from decathlon_voc_analyzer.services.chinese_dataset_service import ChineseDatasetService


def main() -> None:
    parser = argparse.ArgumentParser(description="导出单产品中文审核数据集")
    parser.add_argument("--category", required=True, help="原始类目，例如 backpack")
    parser.add_argument("--product-id", required=True, help="原始产品 ID，例如 backpack_010")
    parser.add_argument(
        "--source-root",
        default="Dataset/products",
        help="原始数据集根目录，默认 Dataset/products",
    )
    parser.add_argument(
        "--output-root",
        default="Dataset_zh/products",
        help="中文审核数据集输出根目录，默认 Dataset_zh/products",
    )
    parser.add_argument("--batch-size", type=int, default=25, help="评论翻译批大小")
    args = parser.parse_args()

    source_product_dir = Path(args.source_root) / args.category / args.product_id
    output_product_dir = Path(args.output_root) / args.category / args.product_id

    service = ChineseDatasetService()
    result = service.export_single_product_dataset(
        source_product_dir=source_product_dir,
        output_product_dir=output_product_dir,
        batch_size=args.batch_size,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()