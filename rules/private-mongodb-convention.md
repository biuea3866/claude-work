# [개인] MongoDB 컨벤션

개인 프로젝트용 MongoDB 규칙. `private-mongodb-implementer`가 작성 기준으로, `private-senior-dba`가 설계 기준으로, `private-infra-reviewer`가 검수 기준으로 공통 참조한다 (SSOT).

## 저장소 선택 기준 (MySQL vs MongoDB)

**기본은 MySQL이다.** MongoDB는 아래 근거 중 하나 이상이 있을 때만 채택하고, `private-senior-dba`가 설계 문서(design-db)에 채택 사유를 의무 기록한다.

| 근거 | 예 |
|---|---|
| 스키마가 유동적·문서형 | 사용자 정의 폼, 설정 스냅샷, 외부 API 원본 보관 |
| 대량 적재 + 관계 불필요 | 이벤트 로그, 행동 이력, 수집 데이터 |
| 계층·중첩 구조가 본질 | 트리형 콘텐츠, 중첩 코멘트 |

- 트랜잭션·관계·정합이 중요한 데이터는 MySQL — "Mongo가 편해서"는 채택 사유가 아니다.
- 한 도메인의 데이터를 두 저장소에 중복 보관하려면 SSOT가 어느 쪽인지 명시한다.

## 모델링 (설계 단계 — senior-dba 담당)

- **임베딩 vs 참조**를 컬렉션마다 근거와 함께 결정한다: 함께 조회·함께 변경·상한 있는 크기면 임베딩, 독립 라이프사이클·무한 성장·다방향 참조면 참조(ID 보유).
- 무한 성장 배열 필드 금지 — 상한(cap) 또는 별도 컬렉션으로.
- 문서 크기 16MB 한계를 설계에서 고려 — 대형 payload는 분리.

## 명명

- **도메인 기반 명명 (과도한 추상화 금지)** — 컬렉션·필드에 `events`·`data`·`items`·`info`·`type` 같은 일반 명사 단독 금지. 도메인을 담는다: `events` ✗ → `rental_events` ✓ (BE `no-over-abstract-name`과 동일 원칙).
- 컬렉션: 도메인을 담은 `snake_case` 복수형 — `rental_events`, `user_settings`
- 필드: `camelCase`. 참조 필드는 `{entity}Id` — MySQL PK(Long)를 참조하면 동일 값 보관
- 인덱스 이름 명시: `idx_{컬렉션}_{필드들}` — 자동 생성 이름 금지

## 인덱스

- 인덱스는 **대상 쿼리가 근거** — design-db의 쿼리 패턴 → 인덱스 매핑에 없는 인덱스는 만들지 않는다.
- 복합 인덱스는 ESR(Equality → Sort → Range) 순서로 구성하고 순서 근거를 주석으로.
- TTL 데이터(로그·이벤트)는 TTL 인덱스로 보존 정책을 구현 — 무기한 적재 금지 (근거 명시 시 예외).

## Validation (JSON Schema validator 의무)

- 스키마리스라도 **모든 컬렉션에 `$jsonSchema` validator를 건다** — 필수 필드·타입·enum 값을 선언한다. 코드 타입만이 방어선인 상태 금지.
- `validationLevel: "moderate"` 기본 (기존 문서 소급 검증 없이 신규/수정만).
- validator 강화(필수 필드 추가 등)는 파괴적 변경 — 기존 문서 정합 확인 후 진행.

## 마이그레이션 스크립트

- 위치: 앱 레포 `src/main/resources/mongo/migration/` — `V{YYYYMMddHHmm}__{snake_case_설명}.js` (Flyway 파일 명명과 대칭)
- `mongosh <스크립트>` 로 그대로 실행 가능해야 하고, **멱등**하게 작성한다 (`createIndex`는 재실행 안전, 컬렉션 생성은 존재 확인 후).
- 스크립트 상단 주석에 롤백 방법(역방향 스크립트) 명시.
- 적용 순서는 파일명 타임스탬프 — 실행 이력은 `_migrations` 컬렉션에 기록한다 (스크립트가 직접 insert).

## BE 코드 연동 (private-be-code-convention과 연동)

- MongoDB 접근도 domain interface(`~Repository.kt`) + infrastructure 구현(`~RepositoryImpl.kt`, Spring Data MongoDB) — MySQL과 동일한 Hexagonal 규칙.
- `MongoTemplate`·`Document` 타입이 domain/application에 노출 금지.
- Document 클래스는 infrastructure에 두고, RepositoryImpl이 도메인 타입으로 변환해 반환한다.
- 날짜 필드는 `ZonedDateTime` 기준으로 다루되 저장 변환은 infrastructure에서 처리.

## 파괴적 변경 (실행 전 사용자 확인 필수)

- `dropDatabase()` / `db.<collection>.drop()` / `deleteMany({})` (전체 삭제)
- validator 강화 (`validationLevel: "strict"` 전환 포함)
- 인덱스 제거, TTL 단축

## 완료 기준

- 로컬 MongoDB에서 스크립트 실행 exit 0 + `getIndexes()`/`getCollectionInfos()` 대조
- validator 위반 insert가 거부되는지 1건 이상 재현
- 롤백 스크립트 주석 명시

## 참고 문서

- [private-db-schema-convention](./private-db-schema-convention.md) — MySQL 대칭 규칙
- [private-be-code-convention](./private-be-code-convention.md) — Repository 레이어 규칙
- [private-tdd](./private-tdd.md) — design-db 문서 구조
