# 5 Experimental Setup

## 5.1 Goals

The experiments in this paper are system validation experiments rather than a full benchmark. We validate whether the end-to-end workflow runs, whether intermediate artifacts are structured and auditable, whether runtime policies distinguish full model paths from degraded paths, and whether the evaluation module can produce useful metrics with or without gold labels.

## 5.2 Environment and Stack

The project targets Python 3.11+ and is validated in a Python 3.12 environment. Core dependencies include FastAPI, Pydantic, Pydantic Settings, LangChain, LangGraph, OpenAI SDK, Qdrant Client, Transformers, Torch, Pillow, orjson, and pytest. The API is exposed through FastAPI, and batch execution is provided by `04_scripts/run_workflow.py`.

## 5.3 Data and Artifacts

Raw product data is stored in `01_data/01_raw_products/products/`. Chinese audit data can be exported to `01_data/02_audit_zh_products/products/`. Outputs are organized by stage under `02_outputs/`, including normalized packages, aspect extraction results, indexes and retrieval caches, reports, feedback, replay, HTML reports, and run manifests.

The current data should not be interpreted as a frozen public benchmark. It is used to validate the workflow, schemas, artifacts, and evaluation interfaces. Larger multi-category annotated sets are required for formal retrieval comparisons.

## 5.4 Workflow Protocol

The standard protocol scans the dataset, normalizes the target product, builds text and image indexes, samples and extracts review aspects, plans retrieval questions, performs route-aware recall and reranking, aggregates aspects, generates the report, builds claim attribution and traces, and optionally exports HTML and manifest artifacts.

The main command is:

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --output-format json --export-html --write-manifest
```

Offline validation can disable external LLM calls:

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --no-llm --output-format json
```

## 5.5 Evaluation Metrics

When `retrieval_relevance` labels are available in the manifest or analysis artifact, the evaluator computes Recall@1, Recall@3, Recall@5, MRR, NDCG@3, and NDCG@5, which are standard information retrieval metrics [13]. Without gold labels, the system still reports review, aspect, question, retrieval, evidence coverage, conflict risk, claim support, citation precision, and route contribution statistics.

## 5.6 Automated Tests

The automated test suite covers APIs, dataset services, review services, question generation, index backends, embedding and reranking, retrieval, analysis, HTML export, manifest evaluation, runtime policies, progress tracking, workflow scripts, and multimodal runtime validation. Running:

```bash
.venv/bin/python -m pytest
```

collects and passes 166 tests in the current codebase.
