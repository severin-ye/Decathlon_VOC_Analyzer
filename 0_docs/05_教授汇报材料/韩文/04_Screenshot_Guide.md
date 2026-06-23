# 프로그램 실행 스크린샷 가이드

---

## 요구사항

교수님께서 **실제 실행 화면의 스크린샷**(동영상 아님)을 요구하셨습니다. 아래는 추천하는 6장의 핵심 스크린샷 목록과 촬영 방법입니다.

---

## 스크린샷 목록

### 스크린샷 1: 환경 설치 검증

**촬영 내용**: 터미널에서 `pytest` 실행 결과 (166 passed)

**조작 명령**:
```bash
cd /home/severin/Codelib/Decathlon_VOC_Analyzer
.venv/bin/pytest
```

**예상 화면**: 166 passed 녹색 요약 행.

---

### 스크린샷 2: 프로그램 실행 과정

**촬영 내용**: 터미널에서 전체 파이프라인 실행 로그 (Stage 1~4)

**조작 명령**:
```bash
.venv/bin/python 04_scripts/run_workflow.py \
    --category backpack \
    --product-id backpack_010 \
    --export-html \
    --write-manifest
```

**예상 화면**: Stage 1 ~ Stage 4의 실행 로그, 각 단계의 processing 정보 표시.

---

### 스크린샷 3: 출력 디렉토리 구조

**촬영 내용**: 실행 후 `02_outputs/`의 디렉토리 트리

**조작 명령**:
```bash
tree 02_outputs/ -L 2
# 또는
ls -R 02_outputs/ | head -40
```

**예상 화면**: `1_normalized/`, `2_aspects/`, `3_indexes/`, `4_reports/`, `5_feedback/`, `5_replay/`, `6_html/`, `7_manifests/`의 계층 구조 표시.

> **참고**: 이미 `02_outputs/`에 backpack_060, backpack_071, shoes_001 등의 기존 실행 결과가 있습니다. 스크린샷에 이 파일들이 보이면 "시스템이 과거에 실행되고, 산출물이 보존"됨을 증명할 수 있습니다.

---

### 스크린샷 4: HTML 보고서 페이지 (브라우저)

**촬영 내용**: 브라우저에서 생성된 HTML 보고서 열기

**조작 명령**:
```bash
# 이미 완성된 보고서가 있으므로 브라우저로 바로 열기
xdg-open 02_outputs/6_html/backpack/backpack_010.html 2>/dev/null || \
  firefox 02_outputs/6_html/backpack/backpack_010.html
```

**예상 화면**: 보고서 페이지에 strengths, weaknesses, evidence attribution 등이 포함됨.

> **참고**: backpack_010.html이 이미 존재합니다. 별도 실행 없이 바로 열 수 있습니다. 만약 없으면 `run_workflow.py`를 --export-html 옵션과 함께 실행하세요.

---

### 스크린샷 5: API 서비스 Swagger 페이지

**촬영 내용**: FastAPI 자동 생성 Swagger UI

**조작 명령**:
```bash
# 터미널1: API 서비스 시작
uvicorn decathlon_voc_analyzer.app.api.main:app --reload

# 브라우저 접속
# http://localhost:8000/docs
```

**예상 화면**: 7개 API 엔드포인트 목록, `/health`, `/api/v1/dataset/overview`, `/api/v1/analysis/product` 등 포함.

---

### 스크린샷 6: 분석 보고서 JSON 내용

**촬영 내용**: 편집기/터미널에서 분석 보고서 JSON의 일부 내용 표시

**조작 명령**:
```bash
# 이미 완성된 분석 결과 사용
python3 -m json.tool 02_outputs/4_reports/backpack/backpack_010_analysis.json | head -80

# 또는 backpack_071 (완전한 실험 데이터 있음)
python3 -m json.tool 02_outputs/4_reports/backpack/backpack_071_analysis.json | head -80
```

**예상 화면**: JSON에 strengths, weaknesses, controversies, evidence_gaps, suggestions, claim_attributions 등의 구조화된 필드 표시.

---

## 선택적 추가 스크린샷

| 내용 | 조작 |
|----------------|-----------|
| **상품 데이터 입력** | `cat 01_data/01_raw_products/products/backpack/backpack_010/product.json` |
| **리뷰 데이터 입력** | `cat 01_data/01_raw_products/products/backpack/backpack_010/reviews.json \| python3 -c "import json,sys; d=json.load(sys.stdin); print(f'Total reviews: {len(d[\"reviews\"])}')"` |
| **실험 모니터링 UI** | `cd 04_scripts/experiment_ui && python3 serve_ui.py`，브라우저에서 `http://localhost:8080/experiment.html` 열기 |
| **논문 아키텍처 다이어그램** | `论文_md形式/图片/图1.png` 사용 (시스템 아키텍처 다이어그램) |

---

## 바로 사용 가능한 산출물 경로

다음 파일들이 이미 존재하므로, 재실행 없이 바로 스크린샷을 찍을 수 있습니다:

| 파일 | 설명 |
|-----------|-----------|
| `02_outputs/1_normalized/backpack/backpack_010.json` | 표준화된 증거 패키지 |
| `02_outputs/4_reports/backpack/backpack_010_analysis.json` | 분석 보고서 |
| `02_outputs/4_reports/backpack/backpack_071_analysis.json` | 완전한 실험 데이터 보고서 |
| `02_outputs/6_html/backpack/backpack_010.html` | HTML 보고서 |
| `02_outputs/7_manifests/shoes/shoes_001_run_manifest.json` | 실행 매니페스트 |
| `02_outputs/6_experiments/current/experiment_summary.json` | 실험 매트릭스 요약 |

---

## 교수님 제출용 최종 스크린샷 패키지

```
professor_screenshots/
├── 01_pytest_passed.png          ← 166 tests passed
├── 02_workflow_execution.png      ← run_workflow.py 실행 로그
├── 03_output_tree.png             ← tree 02_outputs/
├── 04_html_report.png             ← 브라우저에서 HTML 보고서 표시
├── 05_swagger_api.png             ← FastAPI /docs 페이지
├── 06_report_json.png             ← 편집기에서 분석 JSON
├── 07_system_architecture.png     ← 论文_md形式/图片/图1.png (선택)
└── README.txt                     ← 각 이미지의 짧은 설명
```
