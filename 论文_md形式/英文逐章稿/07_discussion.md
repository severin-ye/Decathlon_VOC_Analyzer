# 7 Discussion

## 7.1 Why This Design Fits Product VOC Analysis

The main value of the proposed framework does not lie in any isolated module, but in integrating product text, product images, review structures, and final reports into a single evidence loop. This design is particularly suitable for product VOC analysis because product information is inherently multimodal, while reviews are noisy and colloquial. If conclusions are generated directly from reviews, factual grounding becomes weak. If retrieval is only performed over product evidence, user concerns become weakly anchored. The aspect-to-question interface provides a principled bridge between these two information spaces.

## 7.2 Engineering Lessons from the Current Prototype

Three implementation lessons emerge from the current stage. First, the conceptual layers of the method should map cleanly to the implementation layers, reducing friction between design, code, and paper writing. Second, artifacts are more valuable than logs for research-oriented systems. Persisted normalization outputs, aspect outputs, retrieval records, reports, replay files, and manifests make it possible to revisit intermediate reasoning states after the run has finished. Third, real execution paths and fallback paths should coexist. The combination of LLM and heuristic modes, as well as local and Qdrant backends, allows the system to remain reproducible even when external services are unavailable.

## 7.3 Comparison with One-Shot LLM Summarization

One-shot summarization over all product and review inputs can quickly produce natural-language conclusions, but it suffers from three major limitations. First, it is difficult to determine whether a conclusion originates from review text or product evidence. Second, it is difficult to diagnose and repair local failures. Third, it is difficult to accumulate reusable intermediate artifacts for later training, auditing, or evaluation. In contrast, the staged design adopted here sacrifices some simplicity in exchange for clearer objects, greater controllability, and better explainability.

## 7.4 Implications for Future Research

One of the key implications of this study is that multimodal product analysis may be better approached from the perspective of evidence-seeking task reformulation rather than direct multimodal generation. Once review-derived needs are expressed as retrieval questions, a broad range of future extensions becomes natural: finer-grained visual evidence retrieval, stronger user-segment modeling, retrieval-specific evaluation metrics, replay optimization from human feedback, and semi-automatic audit workflows built around HTML review interfaces.

## 7.5 Implications for Paper Development

At the present stage, the most important scholarly task is not to overclaim benchmark-scale results, but to articulate the system design, experimental protocol, and method boundaries in a rigorous way. This provides a stable narrative foundation on top of which larger-scale experiments, stronger visual retrieval, and human evaluation can later be layered without rewriting the central research problem.