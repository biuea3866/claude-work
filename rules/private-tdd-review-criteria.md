---
id: private-tdd-review-criteria
title: "[개인] 설계 문서(TDD) 검수 기준"
scope: task
level: MUST
context: private
---

# [개인] 설계 문서(TDD) 검수 기준

개인 프로젝트 설계 문서를 **구현 시작·사용자 승인 전에** 검수하는 기준. `private-senior-pm`(design.review)이 정합 검증 기준으로, `private-prd-reviewer`가 PRD↔설계 대조 기준으로 참조한다 (SSOT). 문서 구조 자체는 [private-tdd](./private-tdd.md)가 정의한다 — 섹션 목록을 여기에 복제하지 않는다.

목적은 하나다: **설계 누락·모순을 구현 전에 잡는 것.** 구현이 시작되면 wave 전체가 오염된다.

## verdict

- **PASS** — 누락·모순 없음, 사용자 게이트로 진행
- **NEEDS_REVISION** — 아래 항목 위반, 보강 후 재검수 (최대 2회, 이후 사용자 에스컬레이션)

추측 금지 — 모든 지적은 **문서 섹션명 또는 `파일#메서드`로 근거**를 표기한다.

## 1. 필수 섹션 존재

[private-tdd](./private-tdd.md)의 필수 섹션이 하나라도 비었거나 placeholder 면 NEEDS_REVISION. 특히 개인 하네스가 의무로 두는 세 섹션을 우선 확인한다.

| 섹션 | 없으면 |
|---|---|
| Architecture Benchmarking | NEEDS_REVISION — 최소 2개 사례 + URL |
| 시스템 역할 경계 / 인터페이스 시그니처 | NEEDS_REVISION — 구현자 간 해석 차이가 그대로 머지 충돌이 된다 |
| Release Scenario (무중단 배포) | NEEDS_REVISION — 백필 수반 시 데이터 마이그레이션 5단계 포함 |

## 2. 조건부 섹션 필요성 판단

해당 조건인데 섹션이 없으면 지적한다.

| 조건 | 필요 섹션 |
|------|----------|
| 신규 기능·상태 전이·외부 연동 | 실패 경로·동시성·멱등 (타임아웃·재시도·중복 수신·부분 실패) |
| 상태 머신이 있음 | 상태 전이 표 (현재 상태 × 이벤트 → 다음 상태·거부 사유) |
| DB 마이그레이션·파괴적 변경 | Release Scenario 에 롤백 플랜 (역방향 DDL·플래그 OFF) |
| 값 채우기(백필) 수반 | 데이터 마이그레이션 5단계 — Flyway 인라인 백필 DML 금지 |
| API 변경·이관 | FE 영향 분석 |
| 이벤트 도입 | Layer 판단 근거 ([private-be-architecture-rule](./private-be-architecture-rule.md)) — ApplicationEvent vs Kafka |

PRD 에 모니터링·알림 요구사항이 있는데 설계에 관측 지점이 없으면 NEEDS_REVISION.

## 3. 설계 정합성

- AS-IS 진술이 **실제 코드와 일치**하는가 (필요 시 코드를 직접 읽어 확인 — 추측한 AS-IS 는 그 자체가 결함)
- Possible Solutions 에 채택 사유·미채택 대안이 있는가. "지금 규모에 과한 방안"이 미채택으로 명시됐는가 (오버엔지니어링 차단)
- 클래스 역할이 [private-be-code-convention](./private-be-code-convention.md) 레이어 책임과 충돌하지 않는가
- 다이어그램이 [mermaid](./mermaid.md) 규칙을 지키는가 — flowchart `LR`, 노드 15개 이하, `&` 체이닝 금지

## 4. 티켓 분해 검증

[private-ticket](./private-ticket.md)의 강제 게이트를 그대로 적용한다.

- wave 별 너비 분포가 산출물에 있는가. **모든 wave 너비가 1~2인 직선형 DAG 는 분해 실패**
- 같은 wave 내 파일 교집합이 ∅ 인가 (Single Writer per File)
- 공용 테스트 헬퍼·fixture 의 **선점 소유**가 wave 1 계약 티켓에 명시됐는가

## 5. 테스트 계획 커버리지

- Testing Plan 이 레벨별(domain/application/infrastructure/presentation/scenario) 범위를 명시하는가
- 핵심 비즈니스 흐름과 **실패 경로**(타임아웃·중복·권한·빈 결과)의 시나리오가 있는가
- 다이어그램의 분기·예외 경로마다 대응 케이스가 있는가

## 출력 형식

```
## 설계 검수
### verdict: PASS | NEEDS_REVISION
### 누락·모순 (NEEDS_REVISION 시)
- {섹션/근거} — {문제}
### 조건부 섹션 점검
- 실패 경로·롤백·마이그레이션·FE 영향 필요 여부와 충족 결과
### 티켓 분해
- wave 너비 분포 / Single Writer 검증 결과
### 확인됨
- 문제 없는 항목 요약
```

## 참고 문서

- [private-tdd](./private-tdd.md) — 설계 문서 섹션 구조
- [private-ticket](./private-ticket.md) — 티켓 분해·wave 게이트
- [private-code-review-criteria](./private-code-review-criteria.md) — 구현 후 코드 리뷰 등급
