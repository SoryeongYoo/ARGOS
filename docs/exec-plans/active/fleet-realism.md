# 기단 구성 현실화 (후속 항목)

- 근거: [ADR 0007](../../decisions/0007-fleet-sized-for-overlap-free-tails.md) 알려진 한계
- 상태: **미착수, 사람 결정 필요** (`routes.py` 는 사람이 결정하는 영역)

## 현상

기체 겹침 없는 배정에 맞춰 기단을 150대로 늘렸다. 그중 B777-300ER 가 72대다. 실제 대한항공 기단 구성과 크게 다르다.

## 원인

- 모든 편을 ICN 출발 왕복으로 본다. 장거리 편 하나가 기체를 최대 32.7시간 묶는다 (ICN-JNB B777-300ER).
- `routes.py` 에서 B777-300ER 가 주 기종(`aircraft_types[0]`)인 노선이 29개다.

## 선택지 (결정 전)

1. `routes.py` 의 노선별 주 기종을 바꾼다 (예: 일부 중거리 노선을 B787-9, A321neo 로). 블록타임·승객 수·예측 feature 가 바뀐다.
2. 장거리 편을 ICN 왕복이 아닌 모델(목적지 체류, W 패턴)로 바꾼다. footprint 를 쓰는 aircraft·crew·propagation 이 모두 바뀐다 ([conventions](../../conventions.md) ICN 출발 왕복 가정).
3. 현 상태를 합성 데이터의 한계로 두고 유지한다.

## 완료 조건 (착수 시)

- 3년치 스케줄의 기종별 최대 동시 필요 대수를 다시 계산하고 ADR 0007 표를 갱신한다.
- `validate_data.py --strict` 통과, 비교 테스트 digest 갱신 근거 기록.
