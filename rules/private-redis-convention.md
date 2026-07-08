# [개인] Redis 컨벤션 (캐시 / 락 / 랭킹·세션 / pub-sub)

개인 프로젝트용 Redis 규칙. `private-redis-implementer`가 설계 기준으로, `private-infra-reviewer`가 검수 기준으로 공통 참조한다 (SSOT).

## 키 설계

- 이름: `{서비스}:{도메인}:{엔티티}:{식별자}[:{속성}]` — 예: `rental:product:123:view-count`. 콜론 구분, 소문자-케밥.
- **모든 키에 TTL 필수** — 무기한 키는 설계 문서에 근거를 명시한 경우만 허용.
- 키별 자료구조 선택 근거 1줄 — String/Hash/Set/Sorted Set/Stream 중 왜 그것인지.
- `KEYS` 명령 전제 설계 금지 — 스캔이 필요하면 `SCAN` 또는 인덱스 Set을 별도 설계.
- 키 설계는 **계약 문서(md)** 로 산출 — 키 패턴·자료구조·TTL·무효화 트리거·예시 값 테이블. BE 작업자는 이 문서로 구현한다.

## 용도별 원칙

| 용도 | 원칙 |
|---|---|
| 캐시 (look-aside) | 무효화 이벤트 명시 (어떤 쓰기가 어떤 키를 지우는가). TTL은 무효화의 보조 수단. 핫키는 stampede 방지(TTL jitter 또는 논리 만료) |
| 분산 락 | `SET NX PX` 기반. 락 키·리스 타임·획득 실패 정책(대기/즉시 실패)·해제 보장(finally/워치독) 명시. 리스 타임 > 임계 구역 최대 시간 |
| 랭킹·카운터 | Sorted Set/INCR + 크기 상한(트리밍 정책) 명시. 무한 성장 구조 금지 |
| 세션·토큰 | TTL = 만료 정책과 일치. 민감 값 평문 저장은 사용자 확인 필수 |
| pub/sub·큐 | 전달 보장 필요 여부 먼저 판단 — 유실 불가면 Stream(consumer group), 유실 허용이면 pub/sub. 채널·메시지 필드를 계약 문서에 명시 |

## 서버 설정 (docker compose)

- `maxmemory` + eviction 정책을 용도로 결정 — 캐시 전용 `allkeys-lru`, 세션·락 혼용 `volatile-*` 계열. 근거 1줄.
- persistence(RDB/AOF)는 데이터 성격으로 판단해 근거와 함께 설정 — 캐시 전용이면 불필요, 세션·큐가 있으면 AOF 검토.

## BE 코드 연동 (private-be-code-convention과 연동)

- Redis 접근은 infrastructure 레이어에만 — domain/application에 RedisTemplate·Redisson 노출 금지. domain interface(Repository 또는 Gateway) 뒤로 숨긴다.
- 캐시 무효화 지점은 키 계약 문서의 무효화 트리거와 1:1 대응해야 한다.

## 파괴적 변경 (실행 전 사용자 확인 필수)

- `FLUSHALL` / `FLUSHDB`
- 기존 키 네임스페이스 변경 (마이그레이션 계획 필요)
- eviction 정책 변경

## 완료 기준

- 로컬 Redis에 예시 키를 실제로 넣고 `TTL`·자료구조 명령으로 설계 확인 (redis-cli 출력)
- 락 설계는 동시 획득 시나리오를 redis-cli로 재현 (`SET NX PX`)
- Redis를 띄울 수 없으면 검증 불가를 명시하고 `in-progress`

## 참고 문서

- [private-be-code-convention](./private-be-code-convention.md) — infrastructure 레이어 규칙
