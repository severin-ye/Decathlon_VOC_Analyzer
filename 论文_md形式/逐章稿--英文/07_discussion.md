# 7 Discussion

## 7.1 Why Question-Driven Retrieval Fits Product VOC

The difficulty in product VOC analysis is not only summarizing reviews, but also explaining whether review claims are supported by product evidence. Question-driven retrieval adds an intermediate semantic layer: review aspects describe customer concerns, while retrieval questions describe evidence needs that product text or images can answer.

This is suitable for e-commerce because product pages are naturally multimodal and reviews are naturally subjective and noisy. Directly concatenating all information into a model sacrifices controllability, whereas question planning turns feedback into retrievable, evaluable, and attributable units.

## 7.2 Value of Artifact-First Engineering

The system is artifact-first. Normalized evidence packages, aspect extraction results, question caches, retrieval caches, reports, feedback, replay files, HTML exports, and manifests have fixed structures and output locations. Researchers can inspect any stage instead of only reading the final report.

This also lowers review cost. Standardized product packages, aspect objects, retrieval questions, HTML reports, and manifests can be reused to inspect the same product run stage by stage without rerunning the complete model chain.

## 7.3 Comparison with One-Step LLM Summarization

One-step LLM summarization is simple, but it cannot reliably answer where a conclusion came from, whether product text supports it, or whether images support it. Our staged design increases implementation complexity but provides interpretability, reproducibility, and evaluability.

For a research-oriented system, this tradeoff is necessary. Product VOC reports must support evidence inspection if they are to be used in operational or product decisions.

## 7.4 Methodological Implications

The implementation suggests that better evidence organization and query planning may be more important than simply using larger generators. Review aspects, evidence-seeking questions, text routes, image routes, and claim attribution form auditable operation units, allowing the system to organize product VOC analysis without relying on one black-box summary call.

## 7.5 Scope of Applicability

The method is suitable for product analysis scenarios where evidence provenance matters, especially when product pages contain text, images, and reviews. For scenarios that only require quick high-level summaries, the multi-stage system may be heavier than necessary. For highly localized visual quality issues, the current whole-image and rule-based region evidence still requires finer-grained visual models.
