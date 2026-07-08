#!/usr/bin/env bash
# PreToolUse hook (Bash matcher) — [개인 프로젝트 전용] PR 자동머지 게이트.
# 정책: private-code-reviewer 의 p0~p3 지적이 전부 코드에 반영 확인되면 PR 을 자동머지한다.
#       반영 확인의 실행 주체는 private-code-reviewer(재리뷰) — 이 hook 은
#       "반영 확인 없는 머지"를 차단하는 게이트다.
#
#   - `gh pr merge` 에 `# p3-reflected` 토큰이 없으면 exit 2 로 차단.
#   - 재리뷰에서 p0~p3 전부 반영 확인(잔여 지적이 p4/p5 뿐) 시 토큰을 붙여 재호출 → 통과.
#     p4(대안 제안)/p5(정보성)는 머지를 막지 않는다.
# 스코핑: 레포 루트 마커 `.claude/private-project` 가 있는 개인 프로젝트에서만 동작.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/global-hook-guard.sh"
project_owns_hook "$(basename "${BASH_SOURCE[0]}")" && exit 0
source "$(dirname "${BASH_SOURCE[0]}")/lib/private-project-guard.sh"

input=$(cat)
command=$(printf '%s' "$input" | python3 -c "import json,sys;print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || true)
hook_cwd=$(printf '%s' "$input" | python3 -c "import json,sys;print(json.load(sys.stdin).get('cwd',''))" 2>/dev/null || true)

[[ -z "$command" ]] && exit 0
is_private_project "$hook_cwd" || exit 0

# `gh pr merge` (gh -R repo pr merge 등 변형 포함) 만 대상
[[ "$command" =~ (^|[[:space:]\;\&\|])gh([[:space:]]+-[A-Za-z]+[[:space:]]+[^[:space:]]+)*[[:space:]]+pr[[:space:]]+merge([[:space:]]|$) ]] || exit 0

# 우회 토큰: p0~p3 반영 확인 완료 후 명시 (감사 대상)
[[ "$command" == *"p3-reflected"* ]] && exit 0

cat >&2 <<'EOF'
🛑 [private] PR 머지 차단 — 리뷰 지적(p0~p3) 반영 확인이 선행되지 않았습니다.

자동머지 조건: private-code-reviewer 의 p0~p3 지적이 전부 코드에 반영돼야 합니다.

1) private-code-reviewer 로 재리뷰를 수행하세요 — 이전 리뷰의 p0~p3 지적 각각이
   실제 diff 에 반영됐는지 확인 (verdict 가 APPROVED 이거나 잔여 지적이 p4/p5 뿐이어야 함).
2) 전부 반영 확인되면 머지 명령 끝에 토큰을 붙여 재호출하세요:
   gh pr merge <번호> --squash --auto   # p3-reflected

- p4(대안 제안)·p5(정보성)는 머지를 막지 않습니다.
- 반영 확인 없이 토큰만 붙이는 것은 거짓 단언(COMPLETION-RULE 위반)입니다. 감사 대상.
EOF
exit 2
