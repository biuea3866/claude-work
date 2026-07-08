# [개인] PRD 템플릿

개인 프로젝트용 PRD(Product Requirements Document) 구조. `private-prd-writer`가 작성 기준으로, `private-prd-reviewer`가 검수 기준으로, `private-senior-pm`이 정합 검증의 원본으로 참조한다 (SSOT).

## 저장 규칙

- 경로: `/Users/biuea/Desktop/dpdpdndn/프로젝트/{앱 카테고리}/`
- 파일명: `{YYYYMMDD}-{기능명}-prd.md`
- 앱 카테고리가 특정되지 않으면 디렉토리 목록을 확인시키고 사용자가 지정 — 임의로 새 카테고리를 만들지 않는다.

## 필수 구조

```markdown
# {기능명} PRD

## Background
{왜 지금 이 기능인가 — 동기·맥락}

## Problem Definition
{해결하려는 문제, 현재의 불편 (AS-IS)}

## Goals / Non-Goals
{목표와 명시적 비목표 — 범위 밖을 선언해 오버엔지니어링을 차단}

## User Scenarios
{주요 유저 흐름 — 페르소나별, 해피 패스 + 예외 흐름(실패·빈 상태) 필수}

## Benchmarking
| 제품명 | 카테고리 | 참조 패턴 | URL |
{실제 제품 2개 이상 — WebSearch로 조사}

## Functional Requirements
{기능 요구사항 — 번호 부여(FR-1, FR-2...), 우선순위 P0/P1/P2 필수}

## Non-Functional Requirements
{성능·보안·확장성 — 수치로 (P95 500ms, 동시 100명 등)}

## Operations
{모니터링·알림 요구사항 — 배포 후 무엇을 봐야 하는가}

## Success Metrics
{성공 판단 지표 — 측정 가능한 수치 + 측정 방법}

## Milestones
{단계별 범위 — 있을 때만. 1단계는 P0 전부 포함}

## Open Questions
{미결 사항}

## Document History
| 날짜 | 변경 내용 |
```

## 작성 규칙

- **"무엇을"까지만** — "어떻게"(클래스·스키마·기술 선택)는 TDD의 영역. PRD에 쓰지 않는다.
- **가정 금지** — 해석이 갈리는 지점은 작성 전 질문 목록으로 확인. 사소한 디테일만 합리적 초안 + Open Questions 표기.
- **추상 표현 금지, 수치로** — "빠른 응답" ✗ → "P95 500ms 이내" ✓. "여러 곳" ✗ → "3곳" ✓.
- placeholder 섹션 금지 — 해당 없으면 "해당 없음 + 사유" 1줄.
- 기존 PRD와 모순 금지 — 같은 앱 카테고리의 기존 PRD를 먼저 읽는다.
- 문체·약어·용어는 [output-style](./output-style.md) 적용.

## 검수 연계 (private-prd-reviewer)

- 필수 섹션 누락·placeholder → NEEDS_REVISION
- 우선순위(P0/P1/P2) 미부여, 측정 불가 Success Metrics → NEEDS_REVISION
- 유저 시나리오에 예외 흐름 부재 → NEEDS_REVISION
- 코드베이스 충돌(기존 기능·정책과 모순, AS-IS 사실 오류)은 reviewer가 코드를 읽어 확인

## 참고 문서

- [private-tdd](./private-tdd.md) — PRD 승인 후 설계 문서
- [output-style](./output-style.md) — 문체·수치 구체성
