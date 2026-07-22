# [개인] TDD(Technical Design Document) 템플릿

개인 프로젝트용 기술 설계 문서 구조. `private-senior-be`·`private-senior-fe`·`private-senior-dba`가 작성 기준으로, `private-senior-pm`이 정합 검증 기준으로 참조한다 (SSOT). 회사 `tdd-template.md`의 자급자족 복사본 + 개인용 의무 섹션 추가.

## 필수 섹션

```markdown
# {기능명} TDD

## Background
{프로젝트 배경과 동기 — 근거 PRD 경로 명시}

## Overview
{전체 요약 — 무엇을, 왜, 어떻게}

## Terminology
{용어 정의 테이블}

## Define Problem
### AS-IS
{현재 구조와 문제점 — 실제 코드를 읽고 기술, 추측 금지}
### TO-BE
{목표 구조}

## Architecture Benchmarking (의무)
{동일 과제를 푼 경쟁사·동일 제품군 아키텍처 조사 결과}
| 제품/사례 | 해결 방식 | 참고할 패턴 | 미참고 사유 |
{최소 2개. 기술 블로그·아키텍처 공개 자료 URL 병기}

## Possible Solutions
### 방안 비교
| 방안 | 설명 | 왜 채택 | 미채택 대안 |
{각 방안을 풀어서 기술. "지금 규모에 과한 방안"은 미채택 사유로 명시 — 단순함 우선}

## Detail Design
### 시스템 역할 경계 (의무)
{서비스·컴포넌트·인터페이스·클래스 각각의 역할·소유·노출 범위 표}
| 단위 | 역할 | 소유 데이터/책임 | 노출 인터페이스 | 의존 |
### 인터페이스 시그니처
{Repository/Gateway/API 계약을 시그니처 수준까지 확정 — 구현자 간 해석 차이 제거}
### 클래스 역할 정의
#### 도메인 모델
| 클래스명 | 역할 | 핵심 책임 |
#### 서비스 클래스
| 클래스명 | 역할 | 입력 → 출력 | 의존 |
### 실패 경로·동시성·멱등
{타임아웃·재시도·중복 수신·부분 실패 시 상태 / 락 전략 / 멱등 키 — 해피 패스만 있는 설계는 미완성}
### 상태 전이 표 (상태 머신이 있을 때)
| 현재 상태 × 이벤트 | 다음 상태 | 거부 사유 |
### Component Diagram (Mermaid flowchart LR)
### Sequence Diagram (Mermaid)

## ERD
{Mermaid erDiagram — 요약 수준. 컬럼 상세는 design-db, DDL 전문은 마이그레이션에}

## Testing Plan
{레벨별(domain/application/infrastructure/presentation/scenario) 범위 + 핵심 실패 경로 시나리오 — implementer의 TDD(테스트 우선) 입력}

## Release Scenario — 무중단 배포 (의무)
{중단 없이 배포 가능한 단계별 시나리오. 예: 피처 플래그 / 듀얼라이트 → 데이터 마이그레이션 → 정규 배포 전환 / expand-contract 스키마 변경 / 하위 호환 API 버저닝}
- 배포 순서 (스키마 먼저 vs 코드 먼저)
- 단계별 전환 조건
- 롤백 방법 (플래그 OFF·역방향 전환 — 단계마다)

### 데이터 마이그레이션 계획 (백필 수반 시 의무)
신규 컬럼 추가·구조 변경으로 기존/신규 컬럼·테이블에 값을 채워야 하면, **Flyway 인라인 백필 DML(예: `UPDATE ... WHERE`) 금지**를 전제로 아래 5단계를 설계에 명시한다. Flyway는 DDL 전용, 값 채우기는 배치가 수행한다. 대용량 테이블에 단일 `UPDATE`를 걸면 테이블 전체 락으로 배포가 곧 장애다.

| 단계 | 설계에 명시할 것 |
|------|------|
| 1. 듀얼라이트 | 신규 컬럼/테이블 nullable 추가(DDL) + 코드가 기존·신규 경로에 동시 기록 |
| 2. 배치 백필 | Spring Batch 청크(페이지네이션·PK 범위) 단위·커밋 단위·rate limit·멱등(재실행 가능) 설계 |
| 3. 데이터 검증 | 검증 쿼리/배치 — "NULL 잔존·기존≠신규 0건" 판정 기준과 아티팩트 |
| 4. 기능 배포 | 신규 컬럼/테이블을 읽는 기능 배포 (필요 시 NOT NULL·제약 강화는 이 이후 별도 마이그레이션) |
| 5. 배포 후 검증 | 신규 경로 정상 동작 재검증 + 이상 시 롤백(플래그 OFF·이전 태그) |

- 각 단계는 **독립 배포**로 잡고, 단계마다 롤백 지점을 명시한다 (1~3단계는 아무도 신규 값을 안 읽으므로 코드 되돌리기로 안전).

## Open Questions
{설계 중 발견한 미결 사항}

## Document History
| 날짜 | 변경 내용 |
```

## 작성 규칙

- **AS-IS는 실제 코드 근거** — 파일·클래스를 읽고 `파일#메서드` 형식으로 인용한다.
- 방안 비교는 "무엇인가"가 아니라 "설명" — 표만 나열하지 않고 각 방안을 풀어서 기술한다.
- 다이어그램은 [mermaid](./mermaid.md) 규칙 — flowchart `LR`, 노드 15개 이하, `&` 체이닝 금지.
- 추상 표현 금지, 수치로 — "많은 트래픽" ✗ → "P95 500ms, 초당 10건" ✓.
- placeholder 섹션 금지 — 해당 없으면 "해당 없음 + 사유" 1줄.

## FE 설계 문서 적용 시 (design-fe-web / design-fe-app)

FE는 위 구조를 FE 관점으로 치환한다:
- Detail Design → 화면 목록·텍스트 와이어프레임(토스 패턴 명시)·화면별 상태 표(loading/empty/error/success)·컴포넌트 트리·상태관리 설계·API 연동 표·라우팅 흐름
- 테마 토큰 정의 표 (시맨틱 토큰 → 라이트/다크 값 매핑) 의무
- ERD → 생략, Release Scenario → 기능 플래그·점진 공개 관점으로 작성

## DB 설계 문서 적용 시 (design-db)

- Detail Design → 테이블 정의 표(컬럼·타입·NULL·COMMENT·근거)·쿼리 패턴 → 인덱스 매핑 표·용량 추정·보존 정책
- Release Scenario → expand-contract 마이그레이션 순서·락 영향·롤백 지점 + **백필 수반 시 데이터 마이그레이션 5단계 계획**(듀얼라이트 → 배치 백필 → 검증 → 배포 → 배포 후 검증). Flyway 인라인 백필 DML 금지 — 상세는 [private-db-schema-convention](./private-db-schema-convention.md) "데이터 마이그레이션"

## 참고 문서

- [private-ticket](./private-ticket.md) — TDD 확정 후 티켓 분해
- [private-prd-template](./private-prd-template.md) — 입력이 되는 PRD 구조
- [mermaid](./mermaid.md) — 다이어그램 규칙
