---
name: explore
description: 기능/도메인/API/클래스명으로 관련 레포·파일·클래스를 빠르게 찾는다. .architecture/ 스냅샷을 우선 참조하고 필요 시 자동 재생성.
model: opus
user-invocable: true
---

탐색 대상: $ARGUMENTS

스냅샷: !`ls /Users/chobongjun/Desktop/doodlin_workspace/.architecture/ 2>/dev/null | wc -l | tr -d ' '`개 레포 보유

---

**탐색 접근 순서**
1. 아래 도메인 매핑 테이블로 후보 레포 결정
2. `.architecture/<repo>/api-map.md`, `domain-map.md` 읽기 (없으면 `bin/sync-architecture.sh --no-fetch <repo>`)
3. 스냅샷에서 파일 좁힌 후 실제 코드 진입
4. 레이어 순서로 추적: Controller → Facade → Service → Entity ← Repository

> `greeting-new-back/domain-map.md`는 32K 초과 — grep 필터 후 읽기:
> `grep -n "<키워드>" .architecture/greeting/greeting-new-back/domain-map.md | grep -i "facade\|service\|port" | head -40`

---

## 도메인 → 레포 매핑

### BE — 핵심 도메인

| 도메인/기능 | 레포 | 비고 |
|------------|------|------|
| 지원자 (Applicant) | `greeting/greeting-new-back` | Hexagonal 4-레이어 |
| 공고 (Opening) | `greeting/greeting-new-back`, `opening` | opening은 별도 서비스 |
| 평가/면접 (Evaluation) | `greeting/greeting-new-back` | AI Screening 포함 |
| 오케스트레이션 | `greeting/greeting-aggregator` | 10개 adaptor, 80+ Port |
| 워크스페이스 | `greeting-workspace-server` | Kafka: `event.opening.workspace`(Avro) |

### BE — 결제/플랜

| 도메인/기능 | 레포 | 비고 |
|------------|------|------|
| 결제/구독 | `greeting_payment-server` | Toss Payments |
| 플랜 다운그레이드 | `greeting_plan-data-processor` | NestJS, `PLAN_WORKER_KOTLIN_ENABLED` Flag로 Kotlin 이관 중 |

### BE — 인증/인가

| 도메인/기능 | 레포 | 비고 |
|------------|------|------|
| 인증 (AuthN) | `greeting_authn-server` | JJWT HS256, SSO/SAML/OIDC, 2FA |
| 인가 (AuthZ) | `greeting_authz-server` | RBAC — WORKSPACE/OPENING/APPLICANT |
| API Gateway | `greeting-api-gateway` | Spring Cloud Gateway(WebFlux). routes/dev/*.yaml |

### BE — 알림/커뮤니케이션

| 도메인/기능 | 레포 | 비고 |
|------------|------|------|
| 메일/문자/알림톡 | `greeting-communication` | Kafka `queue.doodlin.{mail\|kakao\|sms}.send.*` |
| 발송 엔진 | `doodlin-communication` | 채널별 실제 발송 |
| 실시간 알림 | `greeting-alert-server` | Node.js, WebSocket |

### BE — 분석/파일/배치

| 도메인/기능 | 레포 | 비고 |
|------------|------|------|
| 대시보드 | `greeting_dashboard-back` | QueryDSL 동적 필터, MySQL+MongoDB |
| 엑셀 처리 | `greeting/greeting-new-back` file-processor 모듈 | Apache POI, Presigned URL |
| 만료 지원자 처리 | `greeting-expired_applicant_processor` | Spring Batch, 매일 UTC 15:00 |

### BE — TRM/외부연동/인프라

| 도메인/기능 | 레포 | 비고 |
|------------|------|------|
| TRM | `greeting_trm-server` | MongoDB 검색, ATS↔TRM 매칭 |
| 외부 연동 (잡보드) | `greeting-integration` | JobPlanet/Programmers/Shiftee |
| DB 스키마 | `greeting/greeting-db-schema` | Flyway, ATS 420개+ 마이그레이션 |
| Kafka 토픽 | `greeting-topic` | Terraform. `event.*`/`queue.*`/`cdc.*`/`dlq.*` |
| 공통 라이브러리 | `doodlin-commons`, `spring-kafka` | KafkaMessageProcessor<T>, DLQ 자동 발행 |

### FE

| 도메인/기능 | 레포 | 비고 |
|------------|------|------|
| ATS 메인 | `greeting_front` | |
| 채용 페이지 | `greeting_career-next` | Pages Router, next-i18next |
| 오퍼 레터 | `greeting_interview-next` | App Router |
| 설문/폼 | `greeting_forms-next` | Redux Toolkit + React Query |
| TRM | `greeting_trm_front` | |
