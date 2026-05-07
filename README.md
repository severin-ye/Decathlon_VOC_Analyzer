# Decathlon VOC Analyzer

Official repository for the paper:

**"Decathlon VOC Analyzer: An Evidence-Driven Multimodal VOC Analysis System for Aligning Product Images, Product Text, and User Reviews"**

Status: research prototype and paper artifact. The current codebase provides an executable end-to-end system, structured intermediate artifacts, evaluation manifests, HTML reports, and experiment scripts for system-method validation.

[Paper draft](论文_md形式/) · [Method docs](0_docs/03_论文子模块文档/README.md) · [Experiment guide](0_docs/04_实验运行指南.md) · [API entrypoint](05_src/decathlon_voc_analyzer/app/api/main.py) · [Citation](#citation)

## Overview

Decathlon VOC Analyzer is an evidence-driven multimodal voice-of-customer system for product analysis. Given product descriptions, product images, and user reviews, it extracts aspect-level VOC signals, turns them into evidence-seeking questions, retrieves product text and image evidence, and generates a structured report with claim-level attribution.

The system is designed as a reproducible research artifact: reviews, aspects, questions, retrieval records, reports, evidence attributions, feedback sidecars, replay sidecars, HTML exports, and run manifests are represented as structured objects that can be inspected after each run.

## Key Features

- Rating-aware review sampling with `problem_first`, `balanced`, and `praise_first` profiles.
- Aspect-level review modeling with LLM and non-LLM fallback paths.
- Question-guided retrieval over product text, product images, and default image regions.
- Local JSON index and Qdrant vector-store backends.
- Text embeddings, CLIP image embeddings, text reranking, and Qwen-VL multimodal reranking.
- Evidence-constrained report generation with strengths, weaknesses, controversies, evidence gaps, and suggestions.
- Claim-level attribution to review, product text, image, and image-region evidence.
- Feedback and replay sidecars for later audit or correction.
- Manifest evaluation for retrieval quality, claim support, groundedness, citation precision, and modality contribution.

## System Pipeline

```text
Raw product folder
  product.json + reviews.json + images/
        |
        v
Stage 1. Product evidence standardization
  ProductEvidencePackage with stable text, image, region, and review IDs
        |
        v
Stage 2. VOC demand modeling
  review filtering -> rating-aware sampling -> aspect extraction -> deduplication
        |
        v
Stage 3. Question-guided multimodal retrieval
  aspect questions -> text/image/mixed routes -> recall -> reranking -> cached evidence
        |
        v
Stage 4. Evidence-constrained reporting
  structured VOC report -> claim attribution -> replay sidecar -> HTML and manifest
```

## Installation

The project is a Python package under `05_src/` and requires Python 3.11 or above.

```bash
git clone https://github.com/severin-ye/Decathlon_VOC_Analyzer.git
cd Decathlon_VOC_Analyzer

python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Optional dependencies:

```bash
# Local OpenVINO inference support
pip install -e .[openvino]

# GPU-oriented local model support
pip install -e .[gpu]
```

Tested project assumptions:

- OS: Linux or WSL2-like Unix environment
- Python: `>=3.11`
- Package layout: `package-dir = {"": "05_src"}`
- Main workflow: FastAPI service and `04_scripts/run_workflow.py`
- Main orchestration: LangGraph single-product workflow
- Main schema layer: Pydantic models

## Repository Structure

```text
.
├── 01_data/
│   ├── 01_raw_products/products/        # Raw product folders
│   └── 02_audit_zh_products/products/   # Chinese audit/export dataset
├── 02_outputs/
│   ├── 1_normalized/                    # Normalized evidence packages
│   ├── 2_aspects/                       # Review aspect artifacts
│   ├── 3_indexes/                       # Local indexes, Qdrant stores, caches
│   ├── 4_reports/                       # Structured analysis reports
│   ├── 5_feedback/                      # Feedback sidecars
│   ├── 5_replay/                        # Replay sidecars
│   ├── 6_html/                          # HTML reports and live progress pages
│   ├── 6_experiments/                   # Experiment matrix outputs
│   ├── 7_manifests/                     # Run manifests
│   └── runtime_logs/                    # Batch and monitor logs
├── 03_configs/
│   ├── review_sampling_profiles.json    # Rating-aware sampling profiles
│   └── runtime_execution_policy.json    # Full-power/degradation policy
├── 04_scripts/                          # CLI, validation, export, and ops scripts
├── 05_src/decathlon_voc_analyzer/
│   ├── app/                             # FastAPI routes and runtime settings
│   ├── evaluation/                      # Manifest evaluation service
│   ├── llm/                             # OpenAI-compatible LLM gateway
│   ├── prompts/                         # Prompt registry and variants
│   ├── schemas/                         # Product, review, retrieval, report schemas
│   ├── stage1_dataset/                  # Dataset scan and evidence normalization
│   ├── stage2_review_modeling/          # Sampling, filtering, aspect extraction
│   ├── stage3_retrieval/                # Embedding, index, retrieval, reranking
│   ├── stage4_generation/               # Question planning, reporting, attribution
│   └── workflows/                       # Batch and LangGraph workflows
├── 06_tests/                            # Unit and integration tests
├── 0_docs/                              # Design, module, and experiment docs
└── 论文_md形式/                         # Paper drafts and export scripts
```

## Data Format

Each product is expected to live under a category folder:

```text
01_data/01_raw_products/products/
└── backpack/
    └── backpack_010/
        ├── product.json
        ├── reviews.json
        └── images/
            └── <variant-id>/
                ├── img1.png
                ├── img2.png
                └── ...
```

Minimal `product.json`:

```json
{
  "product_id": "backpack_010",
  "product_name": "Backpacking organizer travel wallet S",
  "model_description": "Product description and specifications.",
  "category": "Hiking > Bags > Bag accessories",
  "variants": [
    {
      "color": "8512010",
      "image_paths": [
        "images/8512010/img1.png",
        "images/8512010/img2.png"
      ]
    }
  ]
}
```

Minimal `reviews.json`:

```json
{
  "product_id": "backpack_010",
  "reviews": [
    {
      "user_id": "user_001",
      "rating": 4,
      "content": "Convenient and good value."
    }
  ]
}
```

The workflow normalizes these files into a `ProductEvidencePackage`, assigning stable IDs to product text blocks, images, generated image regions, and reviews. Later stages preserve these IDs so report claims can be traced back to concrete evidence.

## Quick Start

Run a small offline demo without external LLM calls:

```bash
.venv/bin/python 04_scripts/run_workflow.py \
  --category backpack \
  --product-id backpack_010 \
  --R_5 \
  --no-llm \
  --retrieval-backend local \
  --output-format json \
  --export-html \
  --write-manifest
```

Expected outputs:

```text
02_outputs/
├── 1_normalized/backpack/backpack_010.json
├── 2_aspects/backpack/backpack_010_review_aspects.json
├── 3_indexes/
├── 4_reports/backpack/backpack_010_analysis.json
├── 5_replay/backpack/backpack_010_replay_sidecar.json
├── 6_html/backpack/backpack_010.html
└── 7_manifests/backpack/backpack_010_run_manifest.json
```

Use this command first to verify that the repository, paths, schemas, and workflow are wired correctly. Full model runs require valid model backends and API keys.

## Running the Full Pipeline

Default single-product workflow:

```bash
.venv/bin/python 04_scripts/run_workflow.py
```

Specify category and product:

```bash
.venv/bin/python 04_scripts/run_workflow.py \
  --category backpack \
  --product-id backpack_010
```

Run the Chinese audit dataset:

```bash
.venv/bin/python 04_scripts/run_workflow.py --cn
```

Limit the review pool:

```bash
.venv/bin/python 04_scripts/run_workflow.py \
  --category backpack \
  --product-id backpack_010 \
  --max-reviews 25
```

Resume from existing artifacts:

```bash
.venv/bin/python 04_scripts/run_workflow.py \
  --category backpack \
  --product-id backpack_010 \
  --resume-from-aspects
```

```bash
.venv/bin/python 04_scripts/run_workflow.py \
  --category backpack \
  --product-id backpack_010 \
  --resume-from-analysis-checkpoint
```

## API Service

Start the FastAPI service:

```bash
uvicorn decathlon_voc_analyzer.app.api.main:app --reload
```

Main endpoints:

- `GET /health`
- `GET /api/v1/dataset/overview`
- `POST /api/v1/dataset/normalize`
- `GET /api/v1/index/overview`
- `POST /api/v1/index/build`
- `POST /api/v1/reviews/extract`
- `POST /api/v1/analysis/product`

`/api/v1/reviews/extract` accepts either a stored product ID with optional category, or a temporary review list. `/api/v1/analysis/product` executes review extraction, question planning, retrieval, reranking, aggregation, report generation, and evidence attribution.

## Configuration

Runtime settings are defined in `05_src/decathlon_voc_analyzer/app/core/config.py` and can be overridden through `.env`.

Common model settings:

```text
qwen_plus_model=qwen-plus
qwen_embedding_model=text-embedding-v4
qwen_reranker_model=gte-rerank-v2
qwen_vl_reranker_model=qwen-vl-max-latest
clip_vl_embedding_model=openai/clip-vit-base-patch32
local_embedding_model_name=Qwen/Qwen3-Embedding-0.6B
local_reranker_model_name=Qwen/Qwen3-Reranker-0.6B
local_multimodal_reranker_model_name=Qwen/Qwen3-VL-2B-Instruct
```

Common backend switches:

```text
embedding_backend=api              # api | local_qwen3
image_embedding_backend=clip       # clip | local_qwen3_vl
retrieval_backend=local            # local | qdrant
reranker_backend=api               # api | local_qwen3
multimodal_reranker_backend=qwen_vl # qwen_vl | local_qwen3_vl
```

Supported API key names:

```text
qwen-plus_api or QWEN_PLUS_API_KEY
DeepSeek-V3_api or DEEPSEEK_V3_API_KEY
openai-gpt5_api or OPENAI_GPT5_API_KEY
```

Runtime strictness is controlled by `03_configs/runtime_execution_policy.json`:

```json
{
  "allow_degradation": false,
  "full_power": false
}
```

- `allow_degradation=true` allows fallback paths after model failures, useful for development validation.
- `allow_degradation=false` avoids silent fallback, useful for formal experiments.
- `full_power=true` requires the full model path and disallows LLM-disabled runs.

`get_settings()` is cached. If tests or scripts modify environment variables in-process, clear the settings cache before re-reading configuration.

## Model Backends and Checkpoints

This repository does not include pretrained model weights. It can use remote API models and local Hugging Face-compatible models depending on the configured backend.

| Component | Default | Alternatives |
| --- | --- | --- |
| LLM report generation | `qwen-plus` | OpenAI-compatible gateway settings |
| Text embedding | `text-embedding-v4` | `Qwen/Qwen3-Embedding-0.6B` |
| Image embedding | `openai/clip-vit-base-patch32` | local Qwen3-VL path |
| Text reranking | `gte-rerank-v2` | `Qwen/Qwen3-Reranker-0.6B` |
| Multimodal reranking | `qwen-vl-max-latest` | `Qwen/Qwen3-VL-2B-Instruct` |

For local Qwen models, use:

```bash
.venv/bin/python 04_scripts/download_local_qwen_models.py
```

## Reproducing Paper Artifacts

The current paper positions the project as a system-methodology artifact. The reproducibility target is therefore a complete, inspectable single-product run and an experiment matrix, not a frozen cross-product leaderboard.

| Paper artifact | Command | Main output |
| --- | --- | --- |
| Single-product workflow example | `.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --export-html --write-manifest` | `02_outputs/4_reports/`, `02_outputs/6_html/`, `02_outputs/7_manifests/` |
| Offline workflow validation | `.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --R_5 --no-llm --output-format json --export-html --write-manifest` | Runnable analysis artifact without external LLM calls |
| Manifest metrics | `.venv/bin/python 04_scripts/evaluate_manifests.py 02_outputs/7_manifests` | Retrieval and claim-attribution summary |
| Multimodal runtime check | `.venv/bin/python 04_scripts/validate_multimodal_runtime.py --category backpack --product-id backpack_010` | Runtime validation log and artifacts |
| Experiment matrix | `.venv/bin/python -m decathlon_voc_analyzer.workflows.experiment_runner --categories backpack shoes sunglasses --products-per-category 5 --max-reviews 25 --output-dir ./02_outputs/6_experiments/current` | `experiment_log.jsonl`, `experiment_summary.json` |
| LLM-as-Judge evaluation | `.venv/bin/python -m decathlon_voc_analyzer.workflows.llm_judge_evaluation --experiment-dir ./02_outputs/6_experiments/current --output-dir ./02_outputs/8_evaluations/current` | `evaluation_log.jsonl`, `evaluation_summary.json` |

Experiment conditions implemented in the matrix:

- `full_system`: full system baseline.
- `ablation_no_qp`: without question planning.
- `ablation_no_image`: without image route.
- `ablation_no_rerank`: without reranking.
- `ablation_no_attribution`: without claim attribution.
- `control_lewis2020`: standard RAG-style baseline.
- `control_jarvis`: evidence-graph and LLM-judge baseline.
- `control_vericite`: three-stage citation verification baseline.

For long runs, resume with:

```bash
.venv/bin/python -m decathlon_voc_analyzer.workflows.experiment_runner \
  --categories backpack shoes sunglasses \
  --products-per-category 5 \
  --max-reviews 25 \
  --output-dir ./02_outputs/6_experiments/current \
  --resume
```

## Evaluation

When a run manifest is available, evaluate manifests with:

```bash
.venv/bin/python 04_scripts/evaluate_manifests.py 02_outputs/7_manifests
```

If `retrieval_relevance` labels are present, the evaluation service reports:

- `Recall@1`, `Recall@3`, `Recall@5`
- `MRR`
- `NDCG@3`, `NDCG@5`

Without gold labels, it still reports audit-oriented workflow statistics:

- informative review count
- aspect count and average aspect confidence
- question count and average question confidence
- retrieved evidence count
- evidence coverage, score drift, and conflict risk
- claim support rate, claim grounded rate, and citation precision
- text, image, and mixed-route contribution

## Tests

Run the automated validation suite:

```bash
.venv/bin/pytest
```

Run linting:

```bash
.venv/bin/ruff check .
```

The tests cover dataset normalization, review modeling, prompt registry, retrieval backends, embedding and reranking services, question generation, report generation, HTML export, manifest evaluation, runtime policy checks, workflow entry points, experiment checkpoints, and paper export utilities.

## Useful Scripts

| Task | Command |
| --- | --- |
| Export one product into Chinese audit format | `.venv/bin/python 04_scripts/export_single_product_chinese_dataset.py --category backpack --product-id backpack_010` |
| Export an existing report to HTML | `.venv/bin/python 04_scripts/export_html_report.py --category backpack --product-id backpack_010` |
| Validate multimodal runtime path | `.venv/bin/python 04_scripts/validate_multimodal_runtime.py --category backpack --product-id backpack_010` |
| Clear generated outputs | `.venv/bin/python 04_scripts/clear_generated_outputs.py` |
| Start experiment launcher | `.venv/bin/python 04_scripts/run_experiments.py start` |
| View experiment status | `.venv/bin/python 04_scripts/run_experiments.py status` |

## Limitations

- Current results are system-validation results, not a frozen multi-category benchmark with human-labeled ground truth.
- The repository supports retrieval-strategy ablations, but published claims should distinguish implemented capability from completed ranked comparisons.
- Image evidence currently uses whole images and rule-based default regions; it is not a semantic segmentation or visual grounding system.
- LLM outputs remain prompt- and model-dependent even with schemas, attribution, and fallback paths.
- Feedback and replay sidecars are implemented as audit interfaces, but their quality impact is not yet quantified as a separate human study.
- Product images and reviews may be subject to original website terms and should be handled accordingly when redistributing data.

## Documentation

- `0_docs/03_论文子模块文档/README.md`: module-by-module paper writing notes aligned with the current source tree.
- `0_docs/04_实验运行指南.md`: experiment matrix, LLM-as-Judge evaluation, resume behavior, and monitoring UI.
- `0_docs/01_设计文档/`: design notes and earlier planning material.
- `0_docs/02_技术文档/`: technical notes for local inference, tutorials, and runtime behavior.
- `论文_md形式/`: paper drafts, title pages, references, and export scripts.

## Citation

If you use this repository or build on its system design, please cite:

```bibtex
@misc{ye2026decathlonvoc,
  title = {Decathlon VOC Analyzer: An Evidence-Driven Multimodal VOC Analysis System for Aligning Product Images, Product Text, and User Reviews},
  author = {Ye, Severin and Lee, Dokeun and Liu, Wushuang and Jung, Seowan and Jung, HyunJun and Jeon, Hye and Kim, Jaesoo},
  year = {2026},
  note = {Research prototype and paper artifact}
}
```

Update the venue, DOI, and publication type once the paper is accepted or released as a preprint.

## License and Data Use

No standalone license file is currently included in this repository. Add a repository-level `LICENSE` file before public release.

Recommended release policy:

- Code: release under a clear open-source license such as MIT, Apache-2.0, or BSD-3-Clause.
- Product images and user reviews: do not redistribute unless the original platform terms permit it.
- Dataset annotations and generated artifacts: specify a separate license if they are released.
- Model weights: follow the license of each upstream model or API provider.

This repository is intended for research use. Users are responsible for complying with the terms of the original product pages, images, reviews, APIs, and model providers.

## Contact

For questions about the paper artifact, contact Severin Ye at `6severin9@gmail.com`.
