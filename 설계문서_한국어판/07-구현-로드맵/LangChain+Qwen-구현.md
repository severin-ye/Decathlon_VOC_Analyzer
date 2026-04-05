# LangChain + Qwen 구현

## 구성 요소 역할 분담

- LangChain: 오케스트레이션, structured output, 메시지 조직, 도구 호출을 담당
- ChatQwen: 리뷰 구조화 추출과 최종 생성을 담당
- Qwen3-VL-Embedding: 상품 이미지와 텍스트 리트리벌을 담당
- Qwen3-VL-Reranker: 재정렬을 담당

## 시작 버전 제안

- 먼저 API 방식으로 생성 모델을 연동한다.
- embedding 과 reranker 는 점진적으로 로컬화할 수 있다.
- 먼저 페이지 수준 또는 객체 수준 리트리벌을 수행하고, 처음부터 영역 수준을 강행하지 않는다.

## 최소 가용 기술 조합

- ChatQwen
- Qwen3-VL-Embedding-2B
- Qwen3-VL-Reranker-2B
- Qdrant

## 왜 이렇게 조합하는가

- 1단계 구현 복잡도를 낮춘다.
- 원시 모달 리트리벌 능력을 보장한다.
- 이후 더 세밀한 방안으로 업그레이드할 공간을 남긴다.

## 후속 업그레이드 방향

- 더 강한 embedding 또는 reranker
- 더 복잡한 영역 수준 증거 인덱스
- 더 강한 평가 및 오류 분석 도구 체인
