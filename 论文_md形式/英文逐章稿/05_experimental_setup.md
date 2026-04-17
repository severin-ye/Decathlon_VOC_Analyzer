# 5 Experimental Design

## 5.1 Experimental Objective

Because the present work is still at the prototype-validation stage, the goal of our experiments is not yet to provide a large-scale statistically conclusive benchmark. Instead, we focus on three questions: whether the proposed framework has already formed an end-to-end workflow from raw product data to final reports; whether multimodal retrieval, aspect extraction, and evidence-constrained reporting have been organized into a stable and unified process; and whether the current artifacts, scripts, and tests are sufficient to support manual auditing, error localization, and subsequent research expansion.

Accordingly, the experimental section should be interpreted as a system-validation study rather than a final benchmark paper.

## 5.2 Environment and Software Stack

The experiments run in a Python 3.12 virtual environment with dependencies managed through pyproject.toml. The main software components include FastAPI, Pydantic, LangChain, LangGraph, OpenAI-compatible interfaces, Qdrant Client, Transformers, Torch, and Pillow. The system exposes both API-based and script-based execution paths, enabling interactive use as well as repeatable end-to-end workflows.

In the currently validated runtime, the main retrieval configuration uses text-embedding-v4 for text embeddings, openai/clip-vit-base-patch32 for image embeddings, gte-rerank-v2 for text reranking, and qwen-vl-max-latest for multimodal reranking. When external services are not available, the system can fall back to heuristic paths and local backends.

## 5.3 Validation Assets

The experimental assets consist of representative product samples rather than a frozen large-scale benchmark. The raw product data are stored under 01_data/01_raw_products/products, while the Chinese audit dataset is stored under 01_data/02_audit_zh_products/products.

The current artifact set includes at least two representative products with final analysis outputs: backpack_010 and sunglasses_001. The normalization report for backpack_010 shows 1 normalized product, 200 reviews, and 5 images. The sunglasses_001 artifact, in contrast, illustrates a richer aspect structure: 3 reviews are transformed into 9 extracted aspects and linked to both text and image evidence during analysis. In this paper, we use backpack_010 as a sparse negative-feedback case and sunglasses_001 as a multi-aspect positive-feedback case.

<a id="tab:validation-assets"></a>

| Validation Asset | Current Scale / Status | Primary Purpose |
| --- | --- | --- |
| backpack_010 | 1 product, 200 reviews, 5 images | Validate normalization, negative-case extraction, and sparse-evidence reporting |
| sunglasses_001 | 3 reviews, 9 aspects, text-image retrieval | Validate LLM-based extraction, multi-aspect aggregation, and scene-aware reporting |
| Chinese audit path | Dedicated namespace and prompt variant support | Validate bilingual workflow and manual-review preparation |

*Table 1. Representative validation assets used in this work.*

## 5.4 Workflow Protocol

The single-product workflow proceeds in the following order:

1. Dataset overview
2. Product normalization
3. Text-image evidence indexing
4. Review extraction and question generation
5. Dual-route retrieval and reranking
6. Aggregation and report generation
7. Optional HTML export and manifest persistence

The batch entry script supports category selection, product ID selection, review limits, top-k per route, number of questions per aspect, optional skipping of normalization or indexing, HTML export, manifest writing, and explicit backend switching between local and Qdrant modes. Convenience flags such as --cn and --R_n are also supported for reproducible constrained runs.

## 5.5 Validation Dimensions

We validate the system along four dimensions. First, workflow completeness: whether normalization, indexing, analysis, and export can be executed from a unified entry point. Second, structural consistency: whether extracted review objects, generated questions, retrieval records, and report fields are represented in stable schemas. Third, runtime consistency: whether the validated environment actually enters the intended multimodal runtime path. Fourth, auditability: whether intermediate and final artifacts are sufficiently rich for manual inspection and error localization.

## 5.6 Script-Level and Test-Level Protocol

In addition to representative artifacts, this paper treats workflow scripts and automated tests as part of the experimental protocol. Table 2 summarizes the currently available validation instruments.

<a id="tab:protocol-and-tests"></a>

| Validation Instrument | Current Status | Validation Purpose |
| --- | --- | --- |
| run_workflow.py | Executable end-to-end product workflow | Validate normalization, indexing, analysis, and export pipeline |
| validate_multimodal_runtime.py | Runtime assertions for multimodal path | Validate whether CLIP and Qwen-VL routes are exposed in runtime profiles |
| pipeline.py | Complete paper-export chain | Validate reproducible generation of merged drafts, LaTeX, and PDF |
| Automated test suite | 13 test modules, 43 tests; 42 passed, 1 failed | Validate dataset, review, question, index, analysis, and workflow stability |

*Table 2. Script-level and test-level validation instruments used in this paper.*

The only failing test concerns a prompt-template language assertion: the system prompt is now written in English, whereas the historical test still expects the Chinese string “问题生成器”. This mismatch does not break the end-to-end workflow, but it indicates that localization and validation baselines have not yet been fully synchronized.