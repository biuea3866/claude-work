#!/usr/bin/env bash
# PreToolUse hook (Bash matcher) — `gh pr create` 직전 셀프 코드 리뷰 게이트.
# 정책: PR 생성 명령에 `# self-review-done` 우회 토큰이 없으면 exit 2 로 차단한다.
#       → Claude 가 교차 리뷰(role review.code — /private-implement Step 6, /private-feature review 노드)를
#         먼저 수행하고, 지적을 반영한 뒤
#         명령 끝에 `# self-review-done` 을 붙여 재호출하면 통과한다.
# 비고: shell hook 은 LLM 리뷰를 직접 실행할 수 없으므로, "리뷰 없이 PR 생성"을 차단하는 게이트로 동작한다.
#       (private-block-env-read 와 동일한 exit-2 + 우회 토큰 패턴)

set -euo pipefail

input=$(cat)
command=$(printf '%s' "$input" | python3 -c "import json,sys;print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || true)

[[ -z "$command" ]] && exit 0

# `gh pr create` (gh -R repo pr create / 옵션 포함 변형 친화) 만 대상.
if ! [[ "$command" =~ (^|[[:space:]\;])gh([[:space:]]+-[A-Za-z]+[[:space:]]+[^[:space:]]+)*[[:space:]]+pr[[:space:]]+create([[:space:]]|$) ]]; then
  exit 0
fi

# 우회 토큰: 셀프 리뷰 완료 후 명령에 명시 (감사 대상)
if [[ "$command" == *"self-review-done"* ]]; then
  exit 0
fi

cat >&2 <<'EOF'
🛑 PR 생성 차단 — 셀프 코드 리뷰가 선행되지 않았습니다.

PR 을 만들기 전에 코드 리뷰를 먼저 수행하세요 (role review.code — /private-implement Step 6):
  1) 변경 diff 전수 리뷰 — private-code-review-criteria.md 의 p0~p5 등급 적용
  2) p0~p2 는 수정, p3~p4 는 PR 본문에 명시
  3) 테스트가 실제로 통과했는지 raw 출력으로 확인 (COMPLETION-RULE)

리뷰를 완료했으면, gh pr create 명령 끝에 우회 토큰을 붙여 재호출하세요:
  gh pr create --base main --title "..." --body "..."   # self-review-done

- 이 게이트는 "리뷰 없이 PR 생성"만 막습니다. 리뷰 자체는 Claude 가 수행합니다.
- 정당한 1회성 우회도 동일하게 `# self-review-done` 주석으로 명시 (감사 대상).
EOF
exit 2
