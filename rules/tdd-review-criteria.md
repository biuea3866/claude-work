# TDD 검수 기준 (TDD Review Criteria)

TDD(Technical Design Document) 초안을 **구현 시작·사용자 승인 전에** 검수하는 기준. `/feature` Step 1-D 자동 검수(prd-reviewer)가 참조한다. 목적: 설계 누락·모순을 구현 전에 잡는 것.

## verdict

- **PASS** — 누락·모순 없음, 사용자 게이트로 진행
- **NEEDS_REVISION** — 아래 항목 위반, TDD 보강 후 재검수 (최대 2회)

추측 금지 — 모든 지적은 **TDD 섹션명 또는 `파일#메서드`로 근거**를 표기한다.

## 1. 필수 섹션 존재 ([tdd-template](./tdd-template.md))

Background / Overview / Terminology / Define Problem(AS-IS·TO-BE) / Possible Solutions / Detail Design / ERD / Testing Plan / Release Scenario — 하나라도 비거나 placeholder면 NEEDS_REVISION.

## 2. 조건부 섹션 필요성 판단

해당 조건인데 섹션이 없으면 지적한다:

| 조건 | 필요 섹션 |
|------|----------|
| 신규 기능·상태 전이·외부 연동·플랜 게이트 변경 | **Observability** (지표·알람·대시보드/로그) |
| DB 마이그레이션·파괴적 변경 포함 | **Release Scenario**에 롤백 플랜(역방향 DDL·플래그 OFF 등) |
| API 변경/이관 | **FE 영향 분석** |
| 보안 변경 | **Security Information** |

PRD에 "운영: 모니터링·알림 요구사항"이 있는데 Observability가 없으면 NEEDS_REVISION.

## 3. 설계 정합성

- Define Problem의 AS-IS 진술이 실제 코드와 일치하는가 (필요 시 코드 확인)
- Possible Solutions에 채택 사유·미채택 대안이 있는가 ("설명" 열 사용)
- Detail Design 클래스 역할이 [be-code-convention](./be-code-convention.md) 레이어 책임과 충돌하지 않는가
- 다이어그램 규칙 준수 ([mermaid](./mermaid.md)) — flowchart `LR`, 노드 15개 이하

## 4. 테스트 계획 커버리지

- Testing Plan이 레벨별(domain/application/infra/presentation/scenario) 범위를 명시하는가
- 핵심 비즈니스 흐름·실패 경로(타임아웃·중복·권한)의 테스트 시나리오가 누락되지 않았는가

## 5. 출력 형식

```
## TDD 검수
### verdict: PASS | NEEDS_REVISION
### 누락·모순 (NEEDS_REVISION 시)
- {섹션/근거} — {문제}
### 조건부 섹션 점검
- Observability/롤백/FE/Security 필요 여부와 충족 결과
### 확인됨
- 문제 없는 항목 요약
```

## 참고

- [tdd-template](./tdd-template.md) — TDD 섹션 구조
- [be-code-convention](./be-code-convention.md) — 레이어 책임
- [mermaid](./mermaid.md) — 다이어그램 규칙
