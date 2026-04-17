# Appendix

## A. Main Directories and Their Roles

| Directory | Role |
| --- | --- |
| 01_data | Raw product data and Chinese audit data |
| 02_outputs | Normalization outputs, aspect outputs, indexes, reports, feedback, replay, HTML, and manifests |
| 03_docs | Design documents, technical notes, and citation materials |
| 04_scripts | Workflow execution, export, and multimodal-runtime validation |
| 05_src | Core source code |
| 06_tests | API, service, and workflow tests |

## B. Current API Endpoints

The current system exposes at least the following API routes:

- /health
- /api/v1/dataset/overview
- /api/v1/dataset/normalize
- /api/v1/index/overview
- /api/v1/index/build
- /api/v1/reviews/extract
- /api/v1/analysis/product

## C. Reproducibility Commands

The main workflow can be executed with:

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010
```

The multimodal runtime can be validated with:

```bash
.venv/bin/python 04_scripts/validate_multimodal_runtime.py --category backpack --product-id backpack_010
```

The English paper export pipeline can be executed with:

```bash
.venv/bin/python 论文_md形式/脚本/pipeline.py --en
```

## D. Current Scope of This Draft

This draft is suitable for:

- system-design reporting
- intermediate paper drafts
- project review and defense materials

It is not yet suitable for:

- a final benchmark-oriented submission requiring large-scale quantitative evaluation
- a camera-ready version with complete figures, human annotations, and fully standardized references