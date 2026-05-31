# OCC 대시보드 — UI 킷

ARGOS **운항통제센터(OCC)** 대시보드를 브라우저에서 직접 실행되는 React + JSX 컴포넌트로 고충실도로 재현한 UI 킷입니다.

원본은 **Streamlit + Plotly + DuckDB**로 구현되어 있습니다: [SoryeongYoo/ARGOS](https://github.com/SoryeongYoo/ARGOS)의 `src/argos/ui/dashboard.py`. 이 킷은 Python 스택 없이 디자이너가 목업을 구성할 수 있도록 해당 인터페이스를 외관상 그대로 재현합니다.

## 탭 구성

1. **OCC 운항 관제** — KPI 스트립 · 노선 지도 · 출발 스케줄 · 지연 전파 시뮬레이션 패널 · 회복 시나리오 카드 3개 · 지연 분포 히스토그램
2. **UAM / ACROSS** — 버티포트 네트워크 지도 · ACROSS 비행 계획 제출 폼 · 버티포트 목록 테이블

## 인터랙티브 흐름

1. 사이드바에서 운항 날짜와 트리거 항공편을 선택합니다.
2. 출발 지연을 설정합니다 (슬라이더, 15–300분, 15분 단위).
3. **▶ 시뮬레이션 실행** 클릭 → 연쇄 체인 + 시나리오 3개가 표시됩니다.
4. 시나리오 1 / 2 / 3 **승인** → 성공 토스트로 조치가 기록됩니다.
5. UAM 탭으로 전환 → ACROSS 비행 계획 제출 → 승인/거부 결과 확인.

## 파일 구성

| 파일 | 역할 |
|---|---|
| `index.html` | 진입점 — React, Babel, 컴포넌트 로드, `<App/>` 마운트 |
| `app.jsx` | 루트 컴포넌트, 탭 상태, `useDashboard()` 노출 |
| `components.jsx` | 아톰: `PillButton`, `Badge`, `KPICard`, `Icon`, `Sparkline` |
| `sidebar.jsx` | 운항 날짜 선택기, 트리거 항공편 콤보, 지연 슬라이더, 주요 CTA |
| `tab_occ.jsx` | OCC 운항 관제 탭 콘텐츠 |
| `tab_uam.jsx` | UAM / ACROSS 탭 콘텐츠 |
| `data.jsx` | 모의 `FLIGHTS`, `SCENARIOS`, `VERTIPORTS`, `CORRIDORS` 데이터 |

## 충실도 참고사항

- **레이아웃, 색상, 타이포, 모션**은 디자인 시스템과 1:1 일치.
- **지도와 차트는 SVG 목업**이며 Plotly가 아닙니다. 위경도 좌표와 회랑 데이터는 `src/argos/uav/network.py` 및 대시보드 스케줄 쿼리에서 가져오지만 단순화된 커스텀 SVG로 렌더링됩니다. 이는 의도적 설계 — 이 킷은 시각 목업용이며 프로덕션 렌더링용이 아닙니다.
- **실제 DuckDB 없음.** 항공편 및 시나리오 데이터는 모두 `data.jsx`에 존재합니다.
