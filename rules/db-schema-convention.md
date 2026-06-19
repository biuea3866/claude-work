# DB 스키마 컨벤션 (Flyway / MySQL)

`{db-schema-repo}` 레포의 Flyway 마이그레이션 작성 규칙. `db-schema-writer`가 작성 기준으로, `code-reviewer`/`pr-reviewer`가 SQL 검수 기준으로 공통 참조한다 (단일 기준).

## DDL 작성 규칙

- FK 컬럼 금지 — 애플리케이션 레벨에서 관리
- ENUM 타입 금지 → VARCHAR로 대체
- JSON 컬럼 금지 → 정규화 또는 TEXT
- BOOLEAN 금지 → `TINYINT(1)` 사용
- 날짜 컬럼: `DATETIME(6)` (마이크로초 정밀도)
- 모든 컬럼·테이블에 `COMMENT` 필수
- NOT NULL 컬럼 추가 시: `DEFAULT` 임시값으로 먼저 추가 → 데이터 채우기 → DEFAULT 제거 순서

## 하위 호환 판단

| 변경 | 처리 |
|------|------|
| 컬럼 추가(nullable) | 단일 마이그레이션 가능 |
| 컬럼 추가(not null) | 3단계 분리 (추가 → 백필 → 제약 변경) |
| 컬럼 삭제 | BE 코드에서 참조 제거 확인 후 진행 |
| 컬럼 타입 변경 | 영향도 분석 먼저, 위험하면 사용자에게 확인 요청 |
| 인덱스 추가 | `ALGORITHM=INPLACE, LOCK=NONE` 명시 |

## 파일 명명

- `V{YYYYMMddHHmm}__{snake_case_설명}.sql`
- 예: `V202505121430__add_notification_channel_column.sql`

## 완료 기준

- 작성한 SQL이 로컬 MySQL 8.0에서 오류 없이 실행되는지 `docker run` 또는 기존 테스트 컨테이너로 검증
- 롤백 방법(역방향 DDL) 주석으로 명시
