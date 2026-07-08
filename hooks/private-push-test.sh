#!/usr/bin/env bash
# PreToolUse hook (Bash matcher) — [개인 프로젝트 전용] push 전 테스트 강제 게이트.
# 정책: `git push` 명령에 `# tests-passed` 토큰이 없으면 exit 2 로 차단한다.
#       → 변경 모듈 테스트를 실제로 실행해 exit code 0 을 확인한 뒤,
#         명령 끝에 `# tests-passed` 를 붙여 재호출하면 통과한다 (감사 대상).
# 비고: COMPLETION-RULE 과 동일 원칙 — 테스트는 exit code 로 확인한다.
#       `... | tail` 같은 파이프는 끝 명령의 exit code 만 남겨 실패를 가린다.
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

# `git push` 만 대상 (git -C <dir> push 등 옵션 변형 포함)
[[ "$command" =~ (^|[[:space:]\;\&\|])git([[:space:]]+-[A-Za-z-]+([[:space:]]+[^[:space:]]+)?)*[[:space:]]+push([[:space:]]|$) ]] || exit 0

# 우회 토큰: 테스트 통과 확인 후 명령에 명시 (감사 대상)
[[ "$command" == *"tests-passed"* ]] && exit 0

cat >&2 <<'EOF'
🛑 [private] push 차단 — 테스트 통과 확인이 선행되지 않았습니다.

push 전에 변경 모듈의 테스트를 실제로 실행하고 exit code 로 성공을 확인하세요:
  BE:  ./gradlew :<모듈>:test   (또는 ./gradlew test)
  FE:  npm test && npx tsc --noEmit   (레포 스크립트 기준)

주의: `... | tail` 같은 파이프는 실패를 가립니다 — exit code 를 직접 확인하세요.

테스트가 통과했으면 push 명령 끝에 우회 토큰을 붙여 재호출하세요:
  git push origin <branch>   # tests-passed

- 테스트 실행 없이 토큰만 붙이는 것은 거짓 단언(COMPLETION-RULE 위반)입니다. 감사 대상.
EOF
exit 2
