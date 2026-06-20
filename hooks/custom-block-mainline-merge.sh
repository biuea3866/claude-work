#!/usr/bin/env bash
# PreToolUse hook (Bash matcher) — mainline 직접 머지 차단.
#
# 허용: gh pr merge — PR 생성 시 code-reviewer 에이전트가 이미 검수했으므로 통과.
# 차단: git merge main/dev/stage-* — PR 없는 직접 머지.
# 차단: git rebase main/dev/stage-* — PR 없는 베이스 변경.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/global-hook-guard.sh"
project_owns_hook "$(basename "${BASH_SOURCE[0]}")" && exit 0

input=$(cat)
command=$(printf '%s' "$input" | python3 -c "import json,sys;print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || true)

# gh pr merge — PR 리뷰 흐름을 거쳤으므로 허용
if [[ "$command" =~ (^|[[:space:]\;])gh[[:space:]]+pr[[:space:]]+merge([[:space:]]|$) ]]; then
  exit 0
fi

# git merge <mainline> — 직접 머지 차단
if [[ "$command" =~ (^|[[:space:]\;])git[[:space:]]+merge([[:space:]]+--[^[:space:]]+)*[[:space:]]+([A-Za-z0-9_.-]+/)?(main|master|dev|stage-[A-Za-z0-9._-]+)([[:space:]]|$) ]]; then
  match="git merge ${BASH_REMATCH[3]:-}${BASH_REMATCH[4]}"
elif [[ "$command" =~ (^|[[:space:]\;])git[[:space:]]+rebase([[:space:]]+--[^[:space:]]+)*[[:space:]]+([A-Za-z0-9_.-]+/)?(main|master|dev|stage-[A-Za-z0-9._-]+)([[:space:]]|$) ]]; then
  match="git rebase ${BASH_REMATCH[3]:-}${BASH_REMATCH[4]}"
else
  exit 0
fi

cat >&2 <<EOF
🛑 mainline 브랜치 직접 머지/리베이스는 차단됩니다.

감지된 명령: $match

PR 흐름을 사용하세요:
  1) git push origin <branch>
  2) gh pr create --base <target>
  3) 리뷰 에이전트 통과 후 gh pr merge <PR#> 자동 실행
EOF
exit 2
