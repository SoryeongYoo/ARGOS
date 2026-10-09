# 커밋된 예측 모델과 feature 정합성 테스트

- 근거: [ADR 0005](../../decisions/0005-prediction-not-wired.md), 진단 [V5](../../harness/00-diagnosis.md)
- 상태: 대기

## 목표

커밋된 `models/delay_predictor.lgb` 를 로드했을 때, 모델의 feature 이름과 순서가 `prediction.features.FEATURE_COLS` 와 같은지 테스트로 보장한다. prediction 을 OCC 흐름에 연결하는 작업은 하지 않는다.

## 영향 파일

- 새 파일: `tests/test_prediction/test_model_contract.py`
- 읽기만 하는 파일: `src/argos/prediction/features.py`, `src/argos/prediction/model.py`, `models/delay_predictor.lgb`

## 단계

1. `DelayPredictor.load(path)` 로 모델을 로드하고, 내부 booster 의 `feature_name()` 을 얻는 방법을 확인한다. 현재 `feature_importance()` 가 `self._model.feature_name()` 을 쓴다.
2. `FEATURE_COLS` 와 순서까지 같은지 확인하는 테스트를 작성한다. 범주형 컬럼(`CAT_COLS`)도 맞는지 확인한다.
3. fixture DB 에서 `engineer_features()` 로 만든 입력으로 `predict_proba()` 가 예외 없이 돌고, 0~1 값을 내는지 확인한다.
4. 현재 모델이 이 테스트를 통과하지 못하면 고치지 말고 보고한다. 재학습은 `train_model.py --yes` 이고 커밋된 파일을 바꾸므로 사람이 결정한다.

## 완료 조건

- 새 테스트가 통과하고, `python scripts/verify.py` 가 통과한다.
- `FEATURE_COLS` 를 바꾸면 이 테스트가 실패한다. 일부러 바꿔 보고 확인한 뒤 원복한다.

## 위험

- LightGBM 이 범주형 feature 를 저장하는 방식이 버전에 따라 다를 수 있다. TODO(확인 필요)
- `.dockerignore` 가 `models/*.lgb` 를 제외하므로, Docker 안에서 돌리면 모델 파일이 없을 수 있다. 테스트는 로컬과 CI 에서만 돈다.
