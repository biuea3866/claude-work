# 코드 리뷰 기준 (Code Review Criteria)

`code-reviewer` / `pr-reviewer` 공통 검수 기준. 두 에이전트는 **출력 채널·모델·컨텍스트 수집만 다르고, 무엇을 어떤 심각도로 보는가는 이 문서가 단일 기준(SSOT)**이다. 등급·체크 항목·출력 형식을 에이전트 본문에 복제하지 않는다.

## 등급(pn) 및 verdict

| 레벨 | 기준 | verdict 영향 |
|------|------|-------------|
| p0 | 보안 취약점·데이터 손실·크래시 위험 | request-changes |
| p1 | harness-rules 위반·아키텍처 레이어 위반·DTO 흐름 위반 | request-changes |
| p2 | 테스트 누락·변수명 축약·메서드 100줄 초과 | request-changes |
| p3 | 네이밍 nit·포맷·사소한 개선 | comment |
| p4 | 대안 제안 (현재 코드도 무방) | comment |
| p5 | 정보성 코멘트 (액션 불필요) | — |

verdict: p0~p2 존재 → **REQUEST_CHANGES** / p3~p4만 → **COMMENT** / 없음 → **APPROVED**

## 검수 전 로드 (필수)

- `.claude/harness-rules.json` — `forbidden_patterns`, `variable_naming`, `integration_test_style` 전수
- [be-code-convention](./be-code-convention.md) — 레이어 책임·UseCase 규칙·Entity Rich Domain·네이밍·DTO·트랜잭션·테스트
- 레포 `CLAUDE.md` — 레포별 오버라이드

## p0 — 보안·데이터

- 인증 없이 노출되는 신규 엔드포인트
- 사용자 입력이 SQL·셸 명령에 직접 보간
- 민감 정보(토큰·비밀번호)가 로그에 출력

## p1 — harness·아키텍처·컨벤션

`harness-rules.json` `forbidden_patterns` 전수 매칭 + [be-code-convention](./be-code-convention.md) 위반:

- 레이어 의존 방향 위반: `presentation → application → domain ← infrastructure` 외 흐름
- Domain/Application 패키지가 Infrastructure를 import
- 도메인 패키지 교차 참조 (`domain.common`만 허용)
- Repository/Gateway/DomainEventPublisher interface가 domain 외에 정의
- Controller → Repository·Entity 직접 참조
- UseCase가 Repository/Gateway/DomainEventPublisher 직접 주입 (DomainService만 허용)
- UseCase 내부 `if + throw` 비즈니스 검증 (Entity/DomainService 위임)
- UseCase `execute()` 10줄 초과 / `@Transactional` 위치가 UseCase 외
- Kafka Consumer/EventListener가 presentation 레이어 외 위치
- Entity가 Anemic Domain (getter/setter만) / 내부 Repository·Gateway·Publisher 주입 / 다른 도메인 Entity 직접 참조 (ID Long만 허용)
- 클래스명 위반: Controller `~ApiController.kt`, UseCase `~UseCase.kt`, Consumer `~EventWorker.kt`
- DTO 흐름 위반: `Request → Command → Entity → Response` 외 / Controller가 Entity를 그대로 응답 반환

**`harness-rules.json` 부재 시 핵심 p1 패턴 (fallback)**

| 패턴 | 대상 |
|------|------|
| `@Query(` (비관적 락 제외) | `*.kt` |
| `ConsumerRecord<String, String>` | `*.kt` |
| `LocalDateTime` | `*.kt` |
| Entity 생성자 `= ""` / `= 0` | `*.kt` |
| `!!` | `*.kt` |
| Consumer 클래스 내 `Repository` 직접 주입 | `*.kt` |
| `@Transactional` in Repository | `*.kt` |
| FK·ENUM 컬럼·JSON 컬럼·BOOLEAN·DATETIME 정밀도 누락 ([db-schema-convention](./db-schema-convention.md)) | `*.sql` |

## p2 — 품질

- 신규 비즈니스 로직에 테스트 없음 (실 DB 없이 Mock만 작성 = harness 위반)
- 변수명 축약 (`ws`, `msg`, `req`, `res`, `cfg` → 풀네임)
- 단일 메서드 100줄 초과

## p3~p4 — nit·대안

- p3: 불필요한 주석, 일관성 없는 네이밍, 소소한 가독성 개선
- p4: 대안 제안 (현재 코드도 무방)

## 공통 원칙

- 변경 파일 **전수 Read** — 요약·추측 금지
- "위험해 보임" 류 추측 코멘트 금지 — 반드시 **파일:라인 + 구체 패턴** 지목
- 컨텍스트(Jira AC·설계 문서)를 읽었다면 코드-설계 불일치는 **p1 이상**으로 올린다

## 출력 형식

```
## 코드 리뷰

### Verdict: REQUEST_CHANGES | COMMENT | APPROVED

### p0 — Critical
- **파일:라인** `문제 코드` → 이유 및 수정 방향

### p1 — Major
- **파일:라인** `문제 코드` → 이유 및 수정 방향

### p2 — Minor
- **파일:라인** 설명

### p3 — Nit
- **파일:라인** 설명

### p4 — Optional
- **파일:라인** 대안 제안

### 확인됨
- 문제 없는 항목 요약
```

해당 레벨에 발견이 없으면 섹션 전체를 생략한다.

## 참고

- [be-code-convention](./be-code-convention.md) — 레이어·UseCase·Entity·네이밍·DTO·트랜잭션·테스트
- [harness-rules.json](../harness-rules.json) — 금지 패턴 전체 목록
- [pr-guide](./pr-guide.md) — 브랜치·PR 템플릿
