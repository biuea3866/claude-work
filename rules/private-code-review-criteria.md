# [개인] 코드 리뷰 기준 (p0~p5)

개인 프로젝트용 코드 리뷰 등급·체크 항목·출력 형식. `private-code-reviewer`가 단일 기준(SSOT)으로 참조하고, `private-infra-reviewer`는 verdict 규칙을 공유한다. 회사 `code-review-criteria.md`의 자급자족 복사본 — 출력은 터미널 전용, GitHub 코멘트 없음.

## 등급(pn) 및 verdict

| 레벨 | 기준 | verdict 영향 |
|------|------|-------------|
| p0 | 보안 취약점·데이터 손실·크래시 위험 | request-changes |
| p1 | 금지 패턴 위반·아키텍처 레이어 위반·DTO 흐름 위반·설계 문서 불일치 | request-changes |
| p2 | 테스트 누락·변수명 축약·메서드 100줄 초과 | request-changes |
| p3 | 네이밍 nit·포맷·사소한 개선 | comment |
| p4 | 대안 제안 (현재 코드도 무방) | comment |
| p5 | 정보성 코멘트 (액션 불필요) | — |

verdict: p0~p2 존재 → **REQUEST_CHANGES** / p3~p4만 → **COMMENT** / 없음 → **APPROVED**

- REQUEST_CHANGES는 wave 게이트를 막는다 — 수정 후 재리뷰 통과 전에는 wave를 닫지 않는다.

## 검수 전 로드 (필수)

- [private-be-code-convention](./private-be-code-convention.md) — BE 금지 패턴 표(no-jpa-query, no-clock-injection 등 전수)·레이어 책임·UseCase·Entity·네이밍·시간 규칙·외부 API 구조·테스트
- [private-be-architecture-rule](./private-be-architecture-rule.md) — 이벤트 기반 아키텍처 (Layer 1 ApplicationEvent / Layer 2 Kafka) 판단·안티패턴
- [private-fe-convention](./private-fe-convention.md) — FE 금지 패턴 표(no-any, no-hardcoded-color 등 전수)·표준 스택·테마 토큰·계층 규칙
- 대상 레포 `CLAUDE.md` — 레포별 오버라이드
- 해당 기능의 설계 문서(`*-tdd.md`, `*-design-fe-*.md`) — 있으면 구현과 대조

## p0 — 보안·데이터

- 인증 없이 노출되는 신규 엔드포인트
- 사용자 입력이 SQL·셸 명령에 직접 보간
- 민감 정보(토큰·비밀번호)가 로그·클라이언트 번들에 출력
- 데이터 손실 가능 로직 (검증 없는 삭제·덮어쓰기)

## p1 — 금지 패턴·아키텍처·계약

### BE — private-be-code-convention "금지 패턴" 표 전수 매칭 + 아래 구조 위반

- 레이어 의존 방향 위반: `presentation → application → domain ← infrastructure` 외 흐름
- 도메인 패키지 교차 참조 (`domain.common`만 허용)
- Repository/Gateway/DomainEventPublisher interface가 domain 외에 정의
- Controller → Repository·Entity 직접 참조 / Entity를 그대로 응답 반환
- UseCase가 Repository/Gateway/Publisher 직접 주입, UseCase 내 `if + throw` 비즈니스 검증, `execute()` 10줄 초과, `@Transactional` 위치가 UseCase 외
- HTTP Client(`XXXClient`)가 GatewayImpl 외부(domain·application)에 노출
- Kafka Consumer/EventListener가 presentation 외 위치
- 이벤트 아키텍처 위반 ([private-be-architecture-rule](./private-be-architecture-rule.md)): UseCase/DomainService에 `ApplicationEventPublisher`·`KafkaTemplate` 직접 주입 / 리스너·EventWorker 내 비즈니스 로직 / Layer 판단 오류(무관 도메인을 ApplicationEvent로 결합, 같은 컨텍스트 서브 도메인을 근거 없이 Kafka로 분리) / Layer 2 구독 멱등 누락 / `@TransactionalEventListener` AFTER_COMMIT 누락
- Anemic Entity / Entity 생성자 기본값 / 다른 도메인 Entity 직접 참조 (ID Long만 허용)
- 클래스명 위반: `~ApiController.kt` / `~UseCase.kt` / `~EventWorker.kt`
- DTO 흐름 위반: `Request → Command → Entity → Response` 외

### FE — private-fe-convention "금지 패턴" 표 전수 매칭 + 아래 위반

- `any`·검증 없는 타입 단언 / 컴포넌트의 `fetch`·`api/` 직접 호출
- 색 하드코딩·한 모드만 구현 (라이트/다크 의무 위반)
- 서버 데이터를 스토어에 복사 보관 / 지역 상태의 전역 승격 (근거 없음)
- loading/empty/error/success 중 상태 처리 누락

### 공통

- **설계 문서와 구현 불일치** — API 계약 필드, 클래스 역할, 상태 전이가 TDD·design 문서와 다르면 p1 이상

## p2 — 품질

- 신규 비즈니스 로직에 테스트 없음 (실 DB 없이 Mock만 작성한 통합 테스트 포함)
- FE: 구현 상세만 검증하는 테스트, snapshot을 동작 검증 대용으로 사용
- 변수명 축약 (`ws`, `msg`, `req`, `cfg` → 풀네임)
- 단일 메서드 100줄 초과 / 컴포넌트 200줄 초과 (분리 미검토)

## p3~p4 — nit·대안

- p3: 불필요한 주석, 일관성 없는 네이밍, 소소한 가독성
- p4: 대안 제안 (현재 코드도 무방)

## 공통 원칙

- 변경 파일 **전수 Read** — diff만 보고 판단 금지, 요약·추측 금지
- "위험해 보임" 류 추측 코멘트 금지 — 반드시 **파일:라인 + 구체 패턴** 지목
- 결과는 터미널 출력만 — GitHub 코멘트·리뷰 등록 없음

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

## 참고 문서

- [private-be-code-convention](./private-be-code-convention.md) / [private-fe-convention](./private-fe-convention.md) — 금지 패턴·컨벤션 원본
- [private-db-schema-convention](./private-db-schema-convention.md) — SQL 검수 (infra-reviewer)
