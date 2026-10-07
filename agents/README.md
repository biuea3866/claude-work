# agents — 페르소나 정의 (27개)

역할·조건·목표를 정의한다. **모델은 여기서 정하지 않는다** — `roles.json` 이 소유한다 (frontmatter `model:` 은 lint 오류).

모든 에이전트는 `roles.json` 바인딩 대상이다 — `role` 열이 그 매핑이다.

| 에이전트 | role | 설명 |
|---|---|---|
| `be-implementer` | — | Kotlin/Spring Boot Hexagonal 구조로 BE 티켓을 TDD 순서(테스트 먼저)로 구현하는 백엔드 IC. T… |
| `code-reviewer` | — | origin push 또는 Draft PR 생성 시 harness-rules 위반·아키텍처 레이어 위반·테스트 누락·보안 이슈… |
| `db-schema-writer` | — | DB 스키마 레포에 Flyway 마이그레이션 SQL을 하위 호환으로 작성하는 DBA. TPM 티켓에 테이블 변경이 포함되면 B… |
| `fe-implementer` | — | FE 레포에서 React/Next.js 컴포넌트를 타입 안전하게 구현하는 FE 개발자. BE API 완료 후 FE 티켓이 생기… |
| `kafka-topic-provisioner` | — | Kafka 토픽 레포에 Terraform으로 Kafka 토픽을 선언하는 인프라 엔지니어. TPM 티켓에 신규 토픽이 포함되면 … |
| `pr-reviewer` | — | PR URL 또는 번호를 받아 변경 파일을 전수 읽고 p0~p5 룰로 리뷰 결과를 터미널에 출력하는 리뷰어. GitHub에 직… |
| `prd-reviewer` | — | PRD/요구사항과 TPM 분석 결과를 검수하는 리뷰어. 누락·오류 검수에 더해, 코드베이스를 직접 읽어 현재 정책과의 충돌·기… |
| `private-architect` | architect | 개인 프로젝트용 아키텍트. 현재 코드베이스를 조사해 지금 트래픽이 현재 서비스 구조에 적합한지 진단하고, 구조적 문제의 해결책… |
| `private-be-implementer` | implement.be | 개인 프로젝트용 BE 작업자. Kotlin/Spring Boot Hexagonal 구조로 요구사항·티켓을 TDD 순서(테스트 … |
| `private-context-analyst` | analyze.context · analyze.cross | 개인 프로젝트용 컨텍스트 분석가. 티켓·요구사항을 받아 수정 범위·레이어별 공개 계약·테스트 케이스·미결 사항을 분석 문서로 산출한다. 서로 다른 런타임 2개가 독립 실행… |
| `private-code-reviewer` | review.code | 개인 프로젝트용 코드 리뷰어 (BE+FE). 브랜치·worktree·diff 범위를 받아 변경 파일을 전수 읽고 p0~p5 등… |
| `private-fe-implementer` | implement.fe | 개인 프로젝트용 FE 작업자. React(웹)·React Native 컴포넌트를 컴포넌트 단위 TDD(테스트 먼저)로 구현한다… |
| `private-infra-reviewer` | review.infra | 개인 프로젝트용 인프라 리뷰어 (MySQL·MongoDB·Kafka·Redis). 마이그레이션 SQL·Mongo 마이그레이션 … |
| `private-kafka-implementer` | implement.kafka | 개인 프로젝트용 Kafka 작업자. 로컬 docker compose 환경에서 토픽 설계(파티션·보존·압축)·JSON 메시지 스… |
| `private-mongodb-implementer` | implement.mongodb | 개인 프로젝트용 MongoDB 작업자. senior-dba의 DB 설계를 받아 컬렉션 생성·인덱스·JSON Schema val… |
| `private-mysql-implementer` | implement.mysql | 개인 프로젝트용 MySQL 작업자. 앱 레포 안 Flyway 마이그레이션(src/main/resources/db/migrati… |
| `private-prd-reviewer` | prd.review | 개인 프로젝트용 PRD 리뷰어. private-prd-writer가 작성한 PRD를 검수한다 — 섹션 누락·모호성·측정 불가 … |
| `private-prd-writer` | prd.author | 개인 프로젝트용 PRD 작업자. 아이디어·요구사항을 받아 전체 구조를 갖춘 PRD를 작성해 /Users/biuea/Deskt… |
| `private-qa` | qa | 개인 프로젝트용 QA. dev 환경(작업 브랜치 → main 머지·배포)에 올라간 기능을 PRD 유저 시나리오 기반 E2E로 … |
| `private-redis-implementer` | implement.redis | 개인 프로젝트용 Redis 작업자. 키 스키마·TTL·자료구조·분산 락·pub/sub 채널을 설계하고 docker compos… |
| `private-senior-be` | design.be | 개인 프로젝트용 시니어 BE. 검수 완료된 PRD를 받아 아키텍처 설계와 TDD(Technical Design Document… |
| `private-senior-dba` | design.db | 개인 프로젝트용 시니어 DBA (MySQL + MongoDB). 검수 완료된 PRD와 BE TDD를 받아 저장소 선택(기본 M… |
| `private-senior-fe` | design.fe | 개인 프로젝트용 시니어 FE. 검수 완료된 PRD와 BE API 계약을 받아 React(웹)·React Native(앱) 기술… |
| `private-senior-pm` | design.review | 개인 프로젝트용 시니어 PM. 시니어 be/fe/dba가 작성한 기술 설계·티켓이 PRD 요구사항을 빠짐없이 커버하는지, 범위… |
| `private-test-author` | test.red | 개인 프로젝트용 RED 테스트 작성자. context.md 공개 계약만 보고 블랙박스 테스트를 작성하고 실패 원인이 미구현인지 확인한 뒤 RED 커밋을 남긴다… |
| `private-tpm` | plan.coordinate | 개인 프로젝트용 TPM(크로스 도메인 조율자). 시니어 be/fe/dba의 설계·티켓을 받아 도메인 간 의존(스키마→BE→FE… |
| `tpm` | — | 요구사항을 받아 영향 서비스·API·Kafka 토픽을 파악하고, 서브 에이전트가 실행할 수 있는 작업 티켓을 의존 그래프(DA… |

## 필수 섹션

`roles.json` 이 참조하는 에이전트는 아래를 포함한다 (lint 강제).

| 섹션 | 목적 |
|---|---|
| `## 역할 경계` | 무엇을 하고 무엇을 하지 않는가 — 범위 침범 차단 |
| `## 출력 형식` | 다음 노드가 파싱할 산출물 골격 |

## 참고

- [roles.json](../roles.json) — role → (agent, runtime, tier) 바인딩
- [docs/decisions/0002-llm-runtime-routing.md](../docs/decisions/0002-llm-runtime-routing.md) — 어느 에이전트가 어느 LLM에서 도는가
