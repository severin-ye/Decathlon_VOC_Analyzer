# 7 Discussion

## 7.1 Why Question-Driven Retrieval Fits Product VOC

The difficulty in product VOC analysis is not only summarizing reviews, but also explaining whether review claims are supported by product evidence. Question-driven retrieval adds an intermediate semantic layer: review aspects describe customer concerns, while retrieval questions describe evidence needs that product text or images can answer.

This is suitable for e-commerce because product pages are naturally multimodal and reviews are naturally subjective and noisy. Directly concatenating all information into a model sacrifices controllability, whereas question planning turns feedback into retrievable, evaluable, and attributable units.

## 7.2 Value of Artifact-First Engineering

The system is artifact-first. Normalized evidence packages, aspect extraction results, question caches, retrieval caches, reports, feedback, replay files, HTML exports, and manifests have fixed structures and output locations. Researchers can inspect any stage instead of only reading the final report.

This also lowers future experiment cost. Standardized product packages can be reused across question generation experiments; aspect and question artifacts can be reused across reranker comparisons; HTML and manifests can support human review.

## 7.3 Comparison with One-Step LLM Summarization

One-step LLM summarization is simple, but it cannot reliably answer where a conclusion came from, whether product text supports it, or whether images support it. Our staged design increases implementation complexity but provides interpretability, reproducibility, and evaluability.

For a research-oriented system, this tradeoff is necessary. Product VOC reports must support evidence inspection if they are to be used in operational or product decisions.

## 7.4 Implications for Future Work

The current implementation suggests that better evidence organization and query planning may be more important than simply using larger generators. Future work can add semantic detection or segmentation for image regions, build multi-category labeled benchmarks, compare retrieval strategies, and integrate feedback/replay with human review interfaces.

## 7.5 Paper-Level Significance

The current paper version provides the main body of a system-methodology paper. It defines the problem, architecture, implementation, evaluation interface, and limitations. Larger quantitative experiments can be added without rewriting the methodological core.
