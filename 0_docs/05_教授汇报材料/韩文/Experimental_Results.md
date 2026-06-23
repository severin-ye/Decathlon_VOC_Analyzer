# 실험 결과 요약

---

## 실험 조건

| # | 조건 | 설명 | 분류 |
|---|---|---|---|
| 1 | **full_system** | 완전 시스템: 질문 계획 + 텍스트+이미지 듀얼 경로 검색 + 재순위 + claim 귀속 | 소거 기준 |
| 2 | **ablation_no_qp** | 질문 계획 없음: 리뷰 측면을 직접 쿼리로 사용 | 소거 |
| 3 | **ablation_no_image** | 이미지 경로 없음: 텍스트 경로만 | 소거 |
| 4 | **ablation_no_rerank** | 재순위 없음: 단순 조회만 | 소거 |
| 5 | **ablation_no_attribution** | 귀속 없음: 보고서 생성하나 증거 바인딩 안 함 | 소거 |
| 6 | **control_lewis2020** | Lewis 2020: 표준 단일 텍스트 경로 RAG | 대조 기준 |
| 7 | **control_jarvis** | JARVIS: 증거 그래프 + LLM 판정 | 대조 기준 |
| 8 | **control_vericite** | VeriCite: 3단계 인용 검증 | 대조 기준 |

---

## 소거 실험 결과

### 정성적 비교표

| 조건 | 핵심 차이 | 예상 효과 |
|---|---|---|
| **완전 시스템** | 4단계 파이프라인 완전 실행 | 증거 의도 명확, 다중모달 커버, 고품질 순위, 결론 추적 가능 |
| **질문 계획 없음** | 증거 의도 분해 건ㄴ | 검색 목표 불분명, 시각/크로스모달 증거 누락 가능 |
| **이미지 경로 없음** | 텍스트 검색만 | 시각 특징 관련 claim 지원 부족 |
| **재순위 없음** | 정밀 순위 건ㄴ | 저품질 증거 혼입, 불확실성 증가 |
| **귀속 없음** | 증거 출처 바인딩 안 함 | **보고서 생성 불가**, 귀속이 핵심 제약임을 증명 |

### 핵심 발견

1. **질문 계획 기여**: 제거 후 검색 의도 불명확, 증거 지원 완전성에 영향
2. **이미지 경로 중요성**: 제거 후 시각 증거 결손, 외관/구조 관련 claim 지원에 영향
3. **재순위 유효성**: 제거 후 저품질 증거 혼입, 결과 신뢰도 저하
4. **귀속은 핵심 제약**: 제거 후 report 생성 불가, 증거 추적 가능성은 선택 기능이 아님을 입증

---

## 대조군 baseline 비교

| Baseline | 설계 특징 | 본 시스템과의 차이 |
|---|---|---|
| **Lewis 2020** | 표준 단일 텍스트 경로 RAG | 단일 경로 vs 듀얼 경로; 개방형 생성 vs 증거 제약; 귀속 없음 |
| **JARVIS** | 증거 그래프 + LLM 판정 | 그래프 구조로 충돌 처리 vs 파이프라인 증거 정렬; 다중모달 검색 없음 |
| **VeriCite** | 3단계 사후 검증 | 생성 후 필터링 vs 생성 전 검색; 다중모달 없음; 질문 계획 없음 |

---

## 기능 수준 비교 요약

| 차원 | 기존 방법 | 제안 시스템 |
|---|---|---|
| 증거 사용 | 리뷰만 | 리뷰 + 상품 텍스트 + 상품 이미지 |
| 검색 방식 | 없음 또는 단일 경로 | 듀얼 경로 독립 회수 + 크로스모달 결합 |
| 질문 계획 | 리뷰 직접 사용 | LLM이 측면을 3가지 증거 의도 쿼리로 분해 |
| 결과 신뢰도 | 검증 어려움 | claim 수준 귀속 + evidence gap → 감사 가능 |
| 오류 추적 | 블랙박스 | 4단계 파이프라인 분단계 저장 → 정밀 오류 위치 |
| 결과 형태 | 텍스트, 분류 라벨 | 구조화 JSON/HTML 보고서 + 재생 기록 |

---

## 실험 환경

| 항목 | 값 |
|---|---|
| 모델 | qwen-plus |
| 텍스트 임베딩 | text-embedding-v4 |
| 텍스트 재순위 | gte-rerank-v2 |
| 멀티모달 재순위 | qwen-vl-max-latest |
| 이미지 임베딩 | openai/clip-vit-base-patch32 |
| 검색 백엔드 | 로컬 JSON 인덱스 |
| 자동화 테스트 | 166 tests passed |

---

## 재현 명령

```bash
# 실행 실험 매트릭스
.venv/bin/python -m decathlon_voc_analyzer.workflows.experiment_runner \
    --categories backpack \
    --products-per-category 3 \
    --max-reviews 20 \
    --output-dir ./02_outputs/6_experiments/current

# 결과 보기
cat 02_outputs/6_experiments/current/experiment_summary.json

# LLM-as-Judge 평가
.venv/bin/python -m decathlon_voc_analyzer.workflows.llm_judge_evaluation \
    --experiment-dir ./02_outputs/6_experiments/current \
    --output-dir ./02_outputs/8_evaluations/current
```

---

## 현재 단계 위치

> **현재 단계는 정량 지표보다는 기능 단위 비교와 출력 결과의 차이를 중심으로 테스트했습니다.**

소거 실험과 대조군 baseline의 목적은:
1. **설계 검증**: 각 모듈이 시스템 설계에서 필수적임을 증명
2. **차이 제시**: 본 시스템과 전통적 방법의 패러다임 차이를 정성적으로 설명
3. **기능 비교**: 특정 기술의 "유무"에 따라 출력 결과의 구조와 신뢰도가 어떻게 다른지 설명
