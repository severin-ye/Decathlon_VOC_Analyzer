from time import perf_counter
import json

from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.stage3_retrieval.reranker_service import RerankerService
from decathlon_voc_analyzer.schemas.index import IndexedEvidence

settings = get_settings()
reranker = RerankerService()

# 使用一个已存在产品的 6 张图像作为候选（backpack_094）
category = "backpack"
product = "backpack_094"
rel_base = "images/8786727"

candidates = []
for i in range(1, 7):
    img_rel = f"{rel_base}/img{i}.png"
    evidence_id = f"{product}_img{i}"
    cand = IndexedEvidence(
        evidence_id=evidence_id,
        product_id=product,
        category_slug=category,
        route="image",
        content=f"Image {i} of product {product}",
        content_original=f"Image {i} of product {product}",
        content_normalized=f"Image {i} of product {product}",
        image_path=img_rel,
    )
    candidates.append(cand)

query = "black backpack strap broken"
print("Settings multimodal_reranker_backend:", settings.multimodal_reranker_backend)
print("Running image rerank micro-benchmark with 6 candidates...")
start = perf_counter()
try:
    results = reranker.rerank(query=query, candidates=candidates, use_llm=True, progress_callback=print, progress_status_callback=print)
    elapsed = perf_counter() - start
    print(f"Elapsed: {elapsed:.3f}s")
    print("Results:")
    print(json.dumps([{"evidence_id": r.evidence_id, "score": r.score} for r in results], ensure_ascii=False, indent=2))
except Exception as e:
    elapsed = perf_counter() - start
    print(f"Exception after {elapsed:.3f}s: {e}")
    raise
