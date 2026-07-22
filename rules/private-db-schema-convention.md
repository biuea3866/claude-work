# [개인] DB 스키마 컨벤션 (Flyway / MySQL 8.0)

개인 프로젝트용 Flyway 마이그레이션 규칙. `private-mysql-implementer`가 작성 기준으로, `private-senior-dba`·`private-infra-reviewer`가 검수 기준으로 공통 참조한다 (SSOT). 회사 `db-schema-convention.md`의 자급자족 복사본.

## 위치

- 마이그레이션은 **앱 레포 안** `src/main/resources/db/migration/` — 별도 스키마 레포를 두지 않는다.

## DDL 작성 규칙

- FK 컬럼 금지 — 참조는 일반 컬럼(`user_id`)으로, 정합성은 애플리케이션 레벨에서 관리
- ENUM 타입 금지 → VARCHAR로 대체
- JSON 컬럼 금지 → 정규화 또는 TEXT
- BOOLEAN 금지 → `TINYINT(1)` 사용
- 날짜 컬럼: `DATETIME(6)` (마이크로초 정밀도)
- 모든 컬럼·테이블에 `COMMENT` 필수
- PK는 `id`로 통일, 참조 컬럼은 `{entity}_id`
- NOT NULL 컬럼 추가 시: `DEFAULT` 임시값으로 먼저 추가 → 데이터 채우기 → DEFAULT 제거 순서
- 인덱스 추가 시: `ALGORITHM=INPLACE, LOCK=NONE` 명시
- **Flyway 마이그레이션에 대용량 백필 DML 금지** — 아래 "데이터 마이그레이션" 참조. Flyway는 **DDL 전용**이다.

## 데이터 마이그레이션 (설계 수준에서 결정 — Flyway 인라인 DML 금지)

신규 컬럼 추가·테이블 구조 변경으로 기존/신규 컬럼·테이블에 값을 채워야 하면 **데이터 마이그레이션**이 수반된다. 이 절차는 **설계 문서(design-db·TDD Release Scenario)에서 먼저 확정**하고, 마이그레이션 파일·배치 코드는 그 설계를 따른다.

### 금지 — Flyway 안의 백필 DML (테이블 전체 락)

```sql
-- ❌ 절대 금지 — products 전체를 잠그고 단일 트랜잭션으로 훑는다 (운영 락·장애)
UPDATE products SET seller_type = 'B2C' WHERE seller_type IS NULL;
```

- Flyway `UPDATE`/`INSERT ... SELECT`로 대용량 테이블을 백필하면 **한 트랜잭션이 대상 행 전체에 락**을 걸어 서비스 쓰기가 막힌다. 배포(마이그레이션 실행)가 곧 장애다.
- Flyway는 **스키마 변경(DDL)만** 담는다. 값 채우기는 아래 5단계로 애플리케이션·배치가 수행한다.
- 예외 — **소규모·정적 시드**(참조 테이블 초기 코드값 등, 수백 행 이내이고 운영 쓰기와 경합 없음)만 Flyway DML 허용. 그 경우 파일 주석에 "대상 행 수 N건, 운영 경합 없음" 근거를 남긴다.

### 5단계 절차 (데이터 마이그레이션이 필요할 때)

| 단계 | 내용 |
|------|------|
| 1. 듀얼라이트 | 신규 컬럼/테이블을 nullable로 추가(DDL, Flyway) → 배포된 코드가 **기존과 신규 경로에 동시 기록**. 이 시점부터 신규로 들어오는 데이터는 채워진다. |
| 2. 배치 백필 | **Spring Batch**로 기존 데이터를 청크 단위(페이지네이션·PK 범위)로 나눠 백필. 청크마다 커밋해 락 범위를 작게, 필요 시 rate limit·야간 실행. 재실행 가능(멱등)하게 작성 |
| 3. 데이터 검증 | 백필 완료 후 정합성 검증 — 검증 쿼리 또는 검증 배치로 "누락(신규 컬럼 NULL 잔존)·불일치(기존≠신규) 0건" 확인. 결과를 아티팩트로 남긴다 |
| 4. 기능 배포 | 검증 통과 후, 신규 컬럼/테이블을 **읽는** 기능을 배포. (필요 시 NOT NULL·제약 강화 DDL은 이 시점 이후 별도 마이그레이션) |
| 5. 배포 후 검증 | 배포 이후 신규 경로가 정상 동작하는지 재검증(검증 쿼리·지표·샘플 확인). 이상 시 롤백(플래그 OFF / 이전 태그 재기동) |

- 각 단계는 **독립 배포**다 — 1·2·3을 한 배포에 몰지 않는다. expand-contract 순서(추가 → 듀얼라이트/백필 → 전환 → 제거)와 동일하다.
- **롤백 지점**을 단계마다 명시한다 — 신규 컬럼은 아직 아무도 안 읽으므로 1~3단계 롤백은 코드 되돌리기로 안전, 최종 제약 강화(DDL)만 역방향 DDL 필요.
- 배치 백필 진행률·검증 결과는 [COMPLETION-RULE](./COMPLETION-RULE.md)의 검증 아티팩트로 남긴다.

## 명명 — 도메인 기반 (과도한 추상화 금지)

테이블·컬럼 이름은 **도메인 개념을 드러내야** 한다. `applications`·`events`·`data`·`items`·`info`·`type`·`status` 같은 일반 명사 단독은 무엇을 담는 테이블/컬럼인지 가리므로 금지한다 (BE `no-over-abstract-name`과 동일 원칙).

- 테이블: 도메인을 담은 `snake_case` 복수형 — `applications` ✗ → `rental_applications` ✓, `events` ✗ → `rental_events` ✓.
- 컬럼: 무엇의 값인지 드러낸다 — `suspend`/`suspended` ✗ → `suspended_at`·`suspended_reason` ✓, `type` ✗ → `payment_method_type` ✓, `status` ✗ → 도메인이 자명한 자기 테이블 안에서는 `status` 허용(예: `rentals.status`), 여러 상태가 공존하면 `rental_status` 등으로 구분.
- 판단 기준: 이름만 보고 "무슨 도메인의 무엇인지" 답할 수 있으면 통과. 공용/모호 테이블명(`applications`·`logs`·`data`)은 반려.
- 상태·구분 값은 VARCHAR(ENUM 금지)로 저장하되 컬럼명에 도메인을 담는다.

## 인덱스 규칙

- 인덱스는 **대상 쿼리가 근거** — 설계 문서(design-db)의 쿼리 패턴 → 인덱스 매핑에 존재하지 않는 인덱스는 만들지 않는다 (쓰기 비용)
- 복합 인덱스는 컬럼 순서 근거(카디널리티·조건 사용 빈도)를 주석으로 명시

## 하위 호환 판단

| 변경 | 처리 |
|------|------|
| 컬럼 추가(nullable, 백필 불필요) | 단일 마이그레이션 가능 |
| 컬럼 추가(백필 필요) / 구조 변경으로 데이터 이관 | "데이터 마이그레이션" 5단계 (듀얼라이트 → 배치 백필 → 검증 → 배포 → 배포 후 검증). **Flyway 인라인 UPDATE 금지** |
| 컬럼 추가(not null) | nullable 추가 → 위 5단계로 백필·검증 → NOT NULL 제약 강화(별도 마이그레이션). 한 마이그레이션에 백필 DML 넣지 않는다 |
| 컬럼 삭제 | BE 코드에서 참조 제거 확인 후 진행 — 참조가 남아 있으면 중단 |
| 컬럼 타입 변경 | 영향도 분석 먼저, 데이터 손실 가능하면 사용자 확인 필수 |
| 테이블 삭제 | 실행 전 사용자 확인 필수 |
| 인덱스 추가 | `ALGORITHM=INPLACE, LOCK=NONE` 명시 |

- 무중단 배포 전제: 모든 변경은 expand-contract 순서(추가 → 듀얼라이트/백필 → 전환 → 제거)로 설계한다. 스키마 먼저/코드 먼저 배포 순서를 마이그레이션 주석 또는 설계 문서에 명시한다.

## 파일 명명

- `V{YYYYMMddHHmm}__{snake_case_설명}.sql`
- 예: `V202607021430__add_notification_channel_column.sql`

## 완료 기준

- 작성한 SQL이 로컬 MySQL 8.0(docker run 또는 테스트 컨테이너)에서 오류 없이 실행되는지 검증 — exit code로 확인
- 기존 마이그레이션 전체 → 신규 순서로 적용해 순서 충돌 없는지 확인
- 롤백 방법(역방향 DDL)을 파일 상단 주석으로 명시

## 참고 문서

- [private-tdd](./private-tdd.md) — 설계 문서 구조 (ERD·데이터 마이그레이션 5단계 계획은 design-db·Release Scenario에, DDL 전문은 마이그레이션에)
- [COMPLETION-RULE](./COMPLETION-RULE.md) — 배치 백필 진행률·검증 결과 아티팩트 기준
