# data_gen

[`src/argos/data_gen/`](../../src/argos/data_gen/)

## 책임

합성 운항 데이터셋(기본 2022–2024, 약 16만 편)을 만들고 품질을 검증한다. 실데이터가 없어서 만든 모듈이므로, 생성 규칙이 곧 "이 세계의 사실"이 된다. API 호출 없이 규칙과 seed 만으로 결정적으로 생성한다.

## 공개 인터페이스

| 모듈 | 진입점 |
|---|---|
| [`routes.py`](../../src/argos/data_gen/routes.py) | `ROUTES`(60개 `RouteDefinition`), `ROUTE_MAP` |
| [`schemas.py`](../../src/argos/data_gen/schemas.py) | Pydantic 모델, `IATA_DELAY_CODES`, `ALL_DDL` |
| [`generator.py`](../../src/argos/data_gen/generator.py) | `SyntheticDataGenerator(settings).run(routes, start, end)`, `FLEET` |
| [`validator.py`](../../src/argos/data_gen/validator.py) | `DataValidator(path).run_all()` → `ValidationReport` |

CLI: `scripts/setup_db.py`, `generate_data.py`, `validate_data.py`. 앞의 둘은 `--yes` 가 없으면 바꿀 내용만 출력한다.

## 데이터 계약

- 테이블: `flights`, `routes`, `route_aircraft`, `aircraft`, `weather_events`, `delay_codes_ref`
- `flights.dep_hour_utc`, `dep_month`, `dep_dow` 는 생성 컬럼이다. 직접 넣지 않는다.
- `generate_data --yes` 는 기간과 무관하게 `flights` 전체를 지우고 다시 쓴다.
- 테스트는 `data/db` 를 읽지 않고 [`tests/conftest.py`](../../tests/conftest.py) 의 `fixture_db_path` 를 쓴다. 이 fixture 는 2024-06-15 하루치를 seed 42 로 만든다.

## 의존해도 되는 대상

`config`, data_gen 내부. 블록타임은 [ADR 0001](../decisions/0001-domain-single-source.md) 에 따라 domain 으로 옮길 대상이다.

## 사람이 결정하는 영역

`routes.py` 의 60개 노선 정의(노선, 기종, 블록타임, 운항 빈도)는 수정하지 말고 제안만 한다.

## 알려진 부채

- **C4**: 블록타임이 `routes.py` 에 하드코딩되어 있고, `domain/block_time` 과 따로 논다.
- **D9**: 출력에 `print`, `logging`, `rich.Console` 이 섞여 있다.
- **D10**: Pydantic 모델(`schemas.py`)과 dataclass(`validator.py`)가 섞여 있다.
- `validator.py` 는 SQL 에 클래스 상수를 f-string 으로 넣는다. 외부 입력은 아니지만 [conventions](../conventions.md) 의 SQL 규칙과 어긋난다.
- F841 `noqa` 6건(`fleet_df` 등)은 DuckDB 가 SQL 안에서 변수 이름으로 읽는 경우라 오탐이다. 지우면 안 된다.
