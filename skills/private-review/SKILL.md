---
name: private-review
description: 개인 프로젝트 코드 리뷰 — PR 번호·브랜치명·인수 없음(현재 브랜치)을 받아 private-code-reviewer(인프라 변경 포함 시 private-infra-reviewer 병행)로 검수한다. 재리뷰에서 p0~p3 전부 반영 확인되면 PR 자동머지까지 수행한다.
user-invocable: true
---

리뷰 대상: $ARGUMENTS  (PR 번호 / 브랜치명 / 비어있으면 현재 브랜치)

현재 브랜치: !`git branch --show-current 2>/dev/null || echo "(git 없음)"`
개인 프로젝트 마커: !`[ -f "$(git rev-parse --show-toplevel 2>/dev/null)/.claude/private-project" ] && echo "OK" || echo "없음"`
기본 base: !`git show-ref --verify --quiet refs/remotes/origin/main && echo "main" || (git remote show origin 2>/dev/null | sed -n 's/.*HEAD branch: //p' || echo "main")`

---

개인 프로젝트 전용 리뷰 진입점. 마커가 없으면 회사용 `/review`를 안내하고 중단한다.

## Step 1 — 리뷰 범위 확정

| 입력 | 범위 |
|------|------|
| PR 번호 `123` | `gh pr view 123 --json files,title,body,baseRefName && gh pr diff 123` |
| 브랜치명 | `git diff origin/<base>...<브랜치> --name-only` → 파일별 Read |
| 비어있음 | `git diff origin/<base>...HEAD --name-only` + 미커밋 변경 포함 |

변경 파일에 인프라 산출물(`db/migration/*.sql`, docker compose, 토픽 스크립트, 이벤트/키 계약 md)이 있는지 분류한다.

## Step 2 — 리뷰어 스폰

**서로 독립이므로 한 메시지에서 동시 스폰한다:**

- `Agent(private-code-reviewer)` — 앱 코드(BE/FE) 변경. 리뷰 범위·레포·브랜치·(재리뷰면) 이전 리뷰 결과를 함께 전달한다.
- `Agent(private-infra-reviewer)` — 인프라 산출물 변경이 있을 때만.

## Step 3 — 결과 처리

- 두 verdict를 병합해 터미널에 그대로 전달한다 (GitHub 코멘트 없음).
- REQUEST_CHANGES → 수정 주체를 명시한다 (사용자가 수정 요청 시 담당 implementer 스폰).

## Step 4 — 재리뷰·자동머지 (PR 대상 + 이전 리뷰가 있을 때)

- private-code-reviewer에게 **재리뷰임을 명시**하고 이전 리뷰의 p0~p3 지적 목록을 전달한다.
- 리뷰어가 지적별 반영 여부를 대조해 **전부 반영 + 신규 p0~p3 없음**이면 스스로 자동머지한다:
  `gh pr merge <번호> --squash --auto   # p3-reflected`
- 미반영이 남으면 머지 없이 미반영 목록을 보고한다. 반영 확인 없이 토큰을 붙이는 것은 금지 (hook `private-auto-merge-gate.sh`가 감사).

## 보고

```
## /private-review 결과
- 대상: {PR/브랜치, 파일 N개}
- 코드 리뷰: {verdict + 등급별 건수}
- 인프라 리뷰: {verdict — 해당 시}
- 자동머지: {실행 여부 + raw 출력 — 재리뷰 시}
- 다음: {REQUEST_CHANGES면 수정 항목}
```
