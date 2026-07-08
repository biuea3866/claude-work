---
name: private-implement
description: 개인 프로젝트 경량 파이프라인 — 설계 문서 없이 요구사항을 바로 해당 작업자(implementer)에게 맡기고 리뷰까지 진행한다. 작은 기능·버그 수정·단일 도메인 변경용. PRD·설계·티켓이 필요한 본격 기능은 /private-feature.
user-invocable: true
---

요구사항: $ARGUMENTS

현재 디렉토리: !`pwd`
개인 프로젝트 마커: !`[ -f "$(git rev-parse --show-toplevel 2>/dev/null)/.claude/private-project" ] && echo "OK" || echo "없음 — 개인 프로젝트가 아니면 이 파이프라인을 쓰지 않는다"`

---

개인 프로젝트 전용 light 파이프라인. 게이트 없이 진행하되, 요구사항 해석이 갈리면 시작 전에 질문한다 (가정 금지).

## Step 1 — 범위 판별

1. 마커가 없으면 중단하고 안내한다.
2. 요구사항이 건드리는 도메인을 판별한다: BE / FE / DB(MySQL·MongoDB) / Kafka / Redis.
3. **3개 이상 도메인 또는 티켓 L 사이즈(~800줄) 초과가 예상되면** 멈추고 `/private-feature`를 제안한다 — 경량 파이프라인의 범위가 아니다.
4. 해석이 갈리는 지점이 있으면 구현 전에 사용자에게 질문한다.

## Step 2 — 선행 인프라 (해당 시)

테이블·컬렉션·토픽·키 변경이 포함되면 구현보다 먼저, 서로 독립이면 **한 메시지에서 동시 스폰**:

- `Agent(private-mysql-implementer)` / `Agent(private-mongodb-implementer)` / `Agent(private-kafka-implementer)` / `Agent(private-redis-implementer)`
- 완료 후 `Agent(private-infra-reviewer)` — REQUEST_CHANGES면 담당 작업자 수정 → 재리뷰 통과까지.

## Step 3 — 구현

- BE: `Agent(private-be-implementer)` / FE: `Agent(private-fe-implementer)` — 둘 다면 BE 먼저(API 계약 확정 후 FE), 무관하면 동시 스폰.
- 각 작업자에게 요구사항 + 도출한 테스트 케이스 후보 + **`origin/main` 기준 숏텀 작업 브랜치 + 전용 worktree** 사용을 지시한다 ([private-branch-convention](../../rules/private-branch-convention.md)). TDD 순서(RED→GREEN→REFACTOR)는 작업자 본문이 강제한다.

## Step 4 — 리뷰

- `Agent(private-code-reviewer)` — worktree diff 리뷰. REQUEST_CHANGES면 담당 implementer에게 수정 지시 → 재리뷰, APPROVED/COMMENT까지 반복.

## Step 5 — 보고

push·PR 생성은 하지 않는다 — 사용자가 요청하면 수행한다 (push는 테스트 exit 0 확인 후 `# tests-passed`, PR base는 `main`, 머지는 `/private-review` 재리뷰 경유 → `main`). 숏텀 브랜치·스택 금지는 [private-branch-convention](../../rules/private-branch-convention.md)을 따른다.

> 완료 단언은 `rules/COMPLETION-RULE.md` §1~4를 모두 충족해야 한다.

```
## /private-implement 결과: {in-progress | 완료}
- 구현: {worktree 경로, 변경 요약}
- 테스트: {레이어별 결과 raw 출력}
- 리뷰: {verdict}
- 다음: {push/PR 원하면 안내}
```
