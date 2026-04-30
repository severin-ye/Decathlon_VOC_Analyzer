# Appendix

## A. Key Directories

| Directory | Responsibility |
| --- | --- |
| `01_data/` | Raw product data and Chinese audit data |
| `02_outputs/` | Normalized packages, aspects, indexes, reports, feedback, replay, HTML, and manifests |
| `03_configs/` | Review sampling profiles and runtime policy configuration |
| `04_scripts/` | Workflow, evaluation, export, validation, and cleanup scripts |
| `05_src/` | Core source code |
| `06_tests/` | API, service, script, and workflow tests |
| `0_docs/03_论文子模块文档/` | Thesis module documents based on current source code |
| `论文_md形式/` | Paper chapters, references, and export scripts |

## B. API Endpoints

The main API endpoints are:

- `/health`
- `/api/v1/dataset/overview`
- `/api/v1/dataset/normalize`
- `/api/v1/index/overview`
- `/api/v1/index/build`
- `/api/v1/reviews/extract`
- `/api/v1/analysis/product`

## C. Reproduction Commands

End-to-end run:

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --output-format json --export-html --write-manifest
```

Offline run:

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --no-llm --output-format json
```

Manifest evaluation:

```bash
.venv/bin/python 04_scripts/evaluate_manifests.py 02_outputs/7_manifests
```

Test suite:

```bash
.venv/bin/python -m pytest
```

English PDF export:

```bash
.venv/bin/python 论文_md形式/脚本/pipeline.py --en
```

## D. Structured Artifacts

| Artifact | Default location | Purpose |
| --- | --- | --- |
| Normalized product package | `02_outputs/1_normalized/` | Input to indexing and analysis |
| Review aspect result | `02_outputs/2_aspects/` | Input to question planning and aggregation |
| Indexes and retrieval cache | `02_outputs/3_indexes/` | Retrieval and reranking reuse |
| Analysis report | `02_outputs/4_reports/` | Final structured VOC output |
| Feedback sidecar | `02_outputs/5_feedback/` | Human feedback entry point |
| Replay sidecar | `02_outputs/5_replay/` | Replay in later runs |
| HTML report | `02_outputs/6_html/` | Human review interface |
| Run manifest | `02_outputs/7_manifests/` | Evaluation and reproducibility entry point |

## E. Scope

This draft is suitable for system design explanation, methodology drafting, project defense, and future experiment planning. It is not yet a complete benchmark paper because multi-category frozen labels, formal ablations, and large-scale human evaluation are still missing.
