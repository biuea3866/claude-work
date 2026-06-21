#!/usr/bin/env bash
# PreToolUse hook (Bash matcher) — mainline 직접 머지 차단.
#
# 허용: gh pr merge — PR 생성 시 code-reviewer 에이전트가 이미 검수했으므로 통과.
# 허용: git rebase --onto <mainline> — feature 브랜치를 최신 main 위로 이동 (안전).
# 허용: git rebase <mainline> — feature 브랜치 rebase (현재 브랜치를 이동, main 미변경).
# 허용: git merge <mainline> — feature 브랜치에서 main 당겨오기 (현재 브랜치가 mainline이 아닐 때).
# 차단: 현재 브랜치가 mainline일 때 git merge <feature> — PR 없는 main 직접 머지.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/global-hook-guard.sh"
project_owns_hook "$(basename "${BASH_SOURCE[0]}")" && exit 0

input=$(cat)
command=$(printf '%s' "$input" | python3 -c "import json,sys;print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || true)

# gh pr merge — PR 리뷰 흐름을 거쳤으므로 허용
if [[ "$command" =~ (^|[[:space:]\;])gh[[:space:]]+pr[[:space:]]+merge([[:space:]]|$) ]]; then
  exit 0
fi

# git rebase (--onto 포함 모든 형태) — feature 브랜치를 이동하는 것이므로 항상 허용
if [[ "$command" =~ (^|[[:space:]\;])git[[:space:]]+rebase([[:space:]]|$) ]]; then
  exit 0
fi

# git merge — 현재 브랜치가 mainline일 때만 차단
# feature 브랜치에서 main을 당겨오는 것(git merge origin/main)은 허용
if [[ "$command" =~ (^|[[:space:]\;])git[[:space:]]+merge([[:space:]]|$) ]]; then
  current_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
  if [[ "$current_branch" =~ ^(main|master|dev|stage-.*)$ ]]; then
    cat >&2 <<EOF
🛑 mainline 브랜치(${current_branch})에서 직접 머지는 차단됩니다.

PR 흐름을 사용하세요:
  1) git push origin <feature-branch>
  2) gh pr create --base ${current_branch}
  3) gh pr merge <PR#>
EOF
    exit 2
  fi
fi

exit 0
