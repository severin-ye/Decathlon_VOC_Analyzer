#!/usr/bin/env python3
"""
本地推理集成演示脚本

演示 Qwen3 小参数模型的集成：
- Qwen3-Embedding-0.6B: 文本嵌入
- Qwen3-Reranker-0.6B: 文本重排
- Qwen3-VL-2B: 多模态图像重排
"""

import sys
from pathlib import Path

# 配置路径
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "05_src"))

from decathlon_voc_analyzer.app.core.config import Settings
from decathlon_voc_analyzer.stage3_retrieval.embedding_service import EmbeddingService
from decathlon_voc_analyzer.stage3_retrieval.reranker_service import RerankerService
from decathlon_voc_analyzer.stage3_retrieval.local_model_utils import (
    LocalEmbeddingModel,
    LocalRerankerModel,
)


def demonstrate_local_models():
    """演示本地模型集成"""
    print("=" * 80)
    print("本地 Qwen3 小参数模型集成演示")
    print("=" * 80)

    # 1. 展示配置
    print("\n📋 当前配置：")
    print("-" * 80)
    settings = Settings()
    print(f"  文本嵌入后端: {settings.embedding_backend}")
    print(f"  图像嵌入后端: {settings.image_embedding_backend}")
    print(f"  文本重排后端: {settings.reranker_backend}")
    print(f"  多模态重排后端: {settings.multimodal_reranker_backend}")
    print(f"  本地嵌入模型: {settings.local_embedding_model_name}")
    print(f"  本地重排模型: {settings.local_reranker_model_name}")
    print(f"  本地多模态模型: {settings.local_multimodal_reranker_model_name}")
    print(f"  设备选择: {settings.local_model_device}")

    # 2. 展示已添加的新方法
    print("\n✨ 新增本地推理方法：")
    print("-" * 80)
    print("  EmbeddingService:")
    print("    ✓ _local_qwen3_embedding() - 使用本地 Qwen3-Embedding-0.6B")
    print("  RerankerService:")
    print("    ✓ _rerank_text_candidates_with_local() - 使用本地 Qwen3-Reranker-0.6B")
    print("    ✓ _rerank_image_candidates_with_local_vl() - 使用本地 Qwen3-VL-2B")

    # 3. 展示后端优先级
    print("\n🔄 推理后端调用优先级：")
    print("-" * 80)
    print("  文本嵌入: api -> local_qwen3 -> hash fallback")
    print("  图像嵌入: clip -> hash fallback")
    print("  文本重排: local_qwen3 -> api -> heuristic fallback")
    print("  图像重排: local_qwen3_vl -> api -> text_api -> heuristic fallback")

    # 4. 展示缓存支持
    print("\n💾 缓存支持：")
    print("-" * 80)
    print("  ✓ 本地推理结果同样支持持久化缓存")
    print("  ✓ 缓存签名区分 api、local_qwen3、heuristic 等后端")
    print("  ✓ 模型变更自动失效缓存")

    # 5. 展示依赖信息
    print("\n📦 所需依赖：")
    print("-" * 80)
    print("  核心:")
    print("    ✓ transformers >= 4.51.0 (Qwen3 支持)")
    print("    ✓ torch >= 2.8.0")
    print("    ✓ numpy >= 1.24.0")
    print("    ✓ pillow >= 11.0.0 (图像处理)")
    print("  可选 (GPU 加速):")
    print("    - flash-attn >= 2.5.0 (FlashAttention-2)")
    print("    - bitsandbytes >= 0.44.0 (模型量化)")

    # 6. 使用示例代码
    print("\n📝 使用示例：")
    print("-" * 80)
    print("""
# 配置切换到本地推理
from decathlon_voc_analyzer.app.core.config import Settings
import os

os.environ["embedding_backend"] = "local_qwen3"
os.environ["reranker_backend"] = "local_qwen3"
os.environ["multimodal_reranker_backend"] = "local_qwen3_vl"

settings = Settings()

# 使用 EmbeddingService 进行文本嵌入
from decathlon_voc_analyzer.stage3_retrieval.embedding_service import EmbeddingService

embedding_service = EmbeddingService()
text = "高性能登山包"
embedding = embedding_service.embed_text(text)  # 使用本地 Qwen3-Embedding-0.6B

# 使用 RerankerService 进行重排
from decathlon_voc_analyzer.stage3_retrieval.reranker_service import RerankerService

reranker_service = RerankerService()
# 将使用本地 Qwen3-Reranker-0.6B 进行文本重排
# 将使用本地 Qwen3-VL-2B 进行图像重排
""")

    # 7. 模型下载提示
    print("\n🔗 模型下载：")
    print("-" * 80)
    print("""
# 模型将在首次使用时从 Hugging Face 自动下载
# 可提前预下载以加速初始化：

from transformers import AutoModel, AutoTokenizer

# 文本嵌入
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3-Embedding-0.6B", trust_remote_code=True)
model = AutoModel.from_pretrained("Qwen/Qwen3-Embedding-0.6B", trust_remote_code=True)

# 文本重排
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3-Reranker-0.6B", trust_remote_code=True)
model = AutoModel.from_pretrained("Qwen/Qwen3-Reranker-0.6B", trust_remote_code=True)

# 多模态（图像+文本）
processor = AutoProcessor.from_pretrained("Qwen/Qwen3-VL-2B-Instruct", trust_remote_code=True)
model = AutoModel.from_pretrained("Qwen/Qwen3-VL-2B-Instruct", trust_remote_code=True)
""")

    print("\n✅ 本地推理集成完成！")
    print("=" * 80)


if __name__ == "__main__":
    demonstrate_local_models()
