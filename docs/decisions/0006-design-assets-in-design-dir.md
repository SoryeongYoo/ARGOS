# 0006. 디자인 자산은 design/ 에서 관리하고, 명시적 요청이 있을 때만 수정한다

- 상태: 승인됨, 적용됨 (2026-10-07, 커밋 0491166)
- 관련 진단: [C6, C7](../harness/00-diagnosis.md)

## 맥락

진단 당시 `src/argos/ui/` 에는 production 코드인 Streamlit `dashboard.py` 와 디자인 시스템 자산이 섞여 있었다 (C7). 자산은 React JSX 목업, 정적 HTML, CSS 토큰, 폰트, 스크린샷, `SKILL.md` 등이다. 그래서 "UI 수정" 요청을 받았을 때 어느 쪽을 고쳐야 하는지 모호했다. UI 문구 규칙은 디자인 문서에만 있었다 (C6).

## 결정

1. 디자인 자산은 [`design/`](../../design/) 에 둔다. `src/argos/ui/` 에는 `dashboard.py` 와 `__init__.py` 만 남긴다.
2. `design/` 은 사용자가 명시적으로 요청할 때만 수정한다. "UI 수정"은 기본적으로 `dashboard.py` 를 고치는 것을 뜻한다.
3. UI 문구와 시각 규칙의 출처는 [`design/README.md`](../../design/README.md) 다.

## 결과

- `git mv` 로 54개 파일을 이동했다. 자산 간 참조는 모두 상대 경로라 그대로 동작한다.
- `design/` 은 `src/` 밖이라 setuptools 패키지에 포함되지 않는다. Dockerfile 은 `src/`, `scripts/`, `notebooks/` 만 복사하므로 이미지에서도 빠진다.
- 남은 차이: `dashboard.py` 는 아직 `design/README.md` 규칙(이모지 금지 등)을 지키지 않는다 (C6). 이 차이는 dashboard 를 수정할 때 함께 정리한다.

## 후속 작업

- 없음. C6 의 규칙 불일치는 [ui 문서](../architecture/ui.md) 의 알려진 부채에 기록한다.
