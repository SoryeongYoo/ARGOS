# 0005. prediction 은 OCC 흐름에 연결하지 않는다 (보류)

- 상태: 승인됨 (2026-10-07)
- 관련 진단: [V5](../harness/00-diagnosis.md), 1.2 의존 방향

## 맥락

- [`src/argos/prediction/`](../../src/argos/prediction/) (LightGBM `DelayPredictor`) 를 쓰는 곳은 [`scripts/train_model.py`](../../scripts/train_model.py) 하나뿐이다. agents 와 ui 는 이 모델을 로드하지 않는다.
- 핵심 흐름의 첫 단계인 "지연 감지"는 실제로는 사람이 트리거 편과 지연 분을 입력하는 방식이다.
- 커밋된 [`models/delay_predictor.lgb`](../../models/delay_predictor.lgb) 가 현재 `features.FEATURE_COLS` 와 맞는지 확인하는 테스트가 없다 (V5).

## 결정

1. prediction 을 OCC 그래프나 대시보드에 연결하지 않는다. 연결 여부는 나중에 따로 결정한다.
2. 보장할 것은 하나다. 커밋된 모델 파일과 현재 코드의 feature 목록과 순서가 일치하는지를 테스트로 확인한다.
3. 연결이 필요해 보여도 에이전트는 구현하지 않고 제안만 한다.

## 결과

- 영향 파일: `tests/` 에 새 테스트 추가. 런타임 코드는 바꾸지 않는다.
- `train_model.py --yes` 로 모델을 다시 학습하면 커밋된 파일이 바뀐다. 이 경우 정합성 테스트가 변경을 드러내야 한다.

## 후속 작업

- [prediction-feature-test](../exec-plans/active/prediction-feature-test.md)
