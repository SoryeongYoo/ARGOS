# 승객 환승 지연 모델링 (미래 항목)

- 근거: [ADR 0001](../../decisions/0001-domain-single-source.md) 갱신 (2026-10-10), [domain-consolidation](../completed/domain-consolidation.md) 5단계
- 상태: **미래**. 착수 결정 전에는 진행하지 않는다

## 목표

지연 전파 결과에 연결 승객(환승) 영향을 넣는다. 앞 편 도착 지연으로 다음 편 연결 시간이 MCT 아래로 떨어지면 환승 실패로 센다.

## 이때 쓸 것

- [`domain/mct.py`](../../../src/argos/domain/mct.py) `get_mct`, `is_connection_valid`, `classify_flight`. 지금은 런타임에 연결하지 않는다.
- MCT 는 승객·승무원 환승 기준이다. 기체 지상 준비 시간인 turn(`domain.fleet.min_turn_minutes`)과 섞지 않는다 ([glossary](../../glossary.md)).

## 착수 전에 필요한 것

- 합성 데이터에 연결 승객(PNR 또는 편 간 환승 인원)이 없다. 데이터 모델부터 정해야 한다.
- ICN 출발 왕복 가정([conventions](../../conventions.md))에서는 ICN 도착 편 → ICN 출발 편 환승만 있다.
