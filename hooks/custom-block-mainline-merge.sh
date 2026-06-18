#!/usr/bin/env bash
# PreToolUse hook (Bash matcher) — main/dev/stage-* 로의 머지를 명시 승인 전까지 차단.
# 사고 패턴: Claude 가 `gh pr merge` 또는 `git merge main/dev` 류를 실수로 실행 → 잘못된 base 의 PR 머지 / 로컬 브랜치 오염.
# custom-block-git-push.sh 의 자매 훅 — push 와 별개로 머지 동사도 가드.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/global-hook-guard.sh"
project_owns_hook "$(basename "${BASH_SOURCE[0]}")" && exit 0

input=$(cat)
command=$(printf '%s' "$input" | python3 -c "import json,sys;print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || true)

# 1) gh pr merge — base 가 main/dev/stage-* 이거나 base 미지정(=레포 기본 브랜치)일 때 모두 가드
# 2) git merge (main|dev|stage-...) — 로컬/원격(origin/, upstream/, <any-remote>/) 머지 명령
# 3) git rebase main / git rebase origin/dev 등 — base 변경도 가드 (rebase 도 remote ref 일관 처리)
if [[ "$command" =~ (^|[[:space:]\;])gh[[:space:]]+pr[[:space:]]+merge([[:space:]]|$) ]]; then
  match="gh pr merge"
elif [[ "$command" =~ (^|[[:space:]\;])git[[:space:]]+merge([[:space:]]+--[^[:space:]]+)*[[:space:]]+([A-Za-z0-9_.-]+/)?(main|master|dev|stage-[A-Za-z0-9._-]+)([[:space:]]|$) ]]; then
  match="git merge ${BASH_REMATCH[3]:-}${BASH_REMATCH[4]}"
elif [[ "$command" =~ (^|[[:space:]\;])git[[:space:]]+rebase([[:space:]]+--[^[:space:]]+)*[[:space:]]+([A-Za-z0-9_.-]+/)?(main|master|dev|stage-[A-Za-z0-9._-]+)([[:space:]]|$) ]]; then
  match="git rebase ${BASH_REMATCH[3]:-}${BASH_REMATCH[4]}"
else
  exit 0
fi

cat >&2 <<EOF
🛑 mainline 브랜치 머지/리베이스는 사용자 명시 승인 후에만 실행할 수 있습니다.

감지된 명령: $match

실행하기 전에 다음을 사용자에게 보고하세요:
  1) 현재 브랜치: \$(git branch --show-current)
  2) base/target 브랜치 (main / dev / stage-*)
  3) gh pr merge 인 경우: PR 번호 + 머지 방식(--squash / --merge / --rebase) + base
  4) 영향 받을 후속 워크플로 (CI 트리거 / 자동 배포)

본 레포 컨벤션:
  - PR 머지는 GitHub UI 또는 사용자가 직접 실행 (CI 보호 + 리뷰 흔적 보존)
  - main 브랜치는 본 모노레포에 존재하지 않음 — dev 가 기본 브랜치
  - feature → feature 머지는 CI 가 안 도므로 base 가 dev/stage-* 인지 반드시 확인
EOF
exit 2
