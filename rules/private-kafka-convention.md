# [개인] Kafka 컨벤션 (로컬 docker compose / JSON 스키마)

개인 프로젝트용 Kafka 규칙. `private-kafka-implementer`가 작성 기준으로, `private-infra-reviewer`가 검수 기준으로 공통 참조한다 (SSOT). 환경 전제: 로컬 docker compose 단일 브로커, Schema Registry 없음(JSON).

## 토픽 규칙

- 이름 형식: 메시지 유형별로 접두사가 갈린다 (**네이밍 유형 SSOT는 [private-be-architecture-rule](./private-be-architecture-rule.md) "토픽 네이밍"**). 소문자, 점 구분.
  - 도메인 이벤트(1:n fan-out): `event.{domain}.{sub-domain}.v{N}` — 예: `event.product.brand-product.v1`. `{sub-domain}`은 도메인 하위 서브 도메인(집계 루트)이며 사건 종류가 아니다. 생성·수정·삭제·상태 전이는 **payload에만** 담고, 한 서브 도메인의 모든 이벤트가 같은 토픽으로 간다.
  - 목적 메시지(1:1 point-to-point): `queue.{action}.v{N}` — 예: `queue.send-email.v1`
- **버전 접미사 `.v{N}`은 필수** — 생략 불가. 최초 토픽이 `.v1`.
- **스키마 파괴 변경은 새 버전 토픽** — in-place 변경 금지. 필드 제거·타입 변경·의미 변경 시 `v{N+1}` 토픽을 새로 만들고 소비자 이관 후 구 토픽 폐기.
- 로컬 개발 기본값: 파티션 3, replication 1. 근거 없이 파티션을 늘리지 않는다.
- retention·cleanup.policy는 이벤트 성격으로 결정 — 상태 스냅샷성은 `compact`, 이벤트 스트림은 `delete` + 보존 기간 명시. 설정마다 결정 근거 1줄.
- **토픽은 명시적으로 생성** — `auto.create.topics.enable` 의존 금지 (설정 오류를 가린다).

## 메시지 스키마 (JSON — 계약 문서가 SSOT)

- 토픽별 **이벤트 계약 문서(md)** 를 작성한다: 토픽명·key·필드 테이블(이름·타입·필수 여부)·예시 payload·호환성 노트. BE 작업자는 이 문서로 DTO를 작성한다.
- 하위 호환 규칙: **필드 추가는 optional만**. 필수 필드 추가·제거·타입 변경은 파괴 변경 → 새 버전 토픽.
- 이벤트 공통 필드 (기본 포함):
  - `eventId` — 멱등 키 (Consumer 중복 처리 기준)
  - `occurredAt` — ISO-8601, 타임존 포함
- **key 설계 명시** — 도메인 이벤트의 라우팅 키는 **그 서브 도메인 엔티티의 PK**(예: `event.product.brand-product.v1`의 key는 brand-product PK). 같은 엔티티 인스턴스의 이벤트가 한 파티션에 모여 순서가 보장된다. 목적 메시지는 순서·분산 기준으로 key를 정한다. key 없는 토픽은 순서 무관함을 계약 문서에 명시.

## Producer / Consumer (BE 코드 — private-be-code-convention과 연동)

- Consumer는 presentation layer `~EventWorker.kt`, `ConsumerRecord<String, String>` 금지, DTO 직접 매핑 + `JsonDeserializer` + `trusted.packages`, UseCase 경유 — 상세는 [private-be-code-convention](./private-be-code-convention.md) "Kafka Consumer".
- Consumer는 `eventId` 기반 멱등 처리를 구현한다 — 중복 수신은 정상 시나리오다.
- Producer는 DomainEventPublisher 구현체(infrastructure)에서만 발행 — 서비스 코드에서 KafkaTemplate 직접 사용 금지.

## 파괴적 변경 (실행 전 사용자 확인 필수)

- 토픽 삭제
- 파티션 수 변경 (key 순서 보장이 깨진다)
- retention 축소, cleanup.policy 변경

## 완료 기준

- 로컬 브로커에 토픽을 실제 생성하고 `kafka-topics --describe`로 설정 확인 (exit code + 출력)
- 예시 payload를 produce/consume해 계약 문서와 일치 확인
- 브로커를 띄울 수 없으면 검증 불가를 명시하고 `in-progress`

## 참고 문서

- [private-be-architecture-rule](./private-be-architecture-rule.md) — Kafka는 이벤트 아키텍처 Layer 2(무관한 도메인). 언제 Kafka로 발행할지의 판단 SSOT
- [private-be-code-convention](./private-be-code-convention.md) — Consumer/Producer 코드 규칙
- [private-tdd](./private-tdd.md) — 설계 문서에 이벤트 흐름 다이어그램
