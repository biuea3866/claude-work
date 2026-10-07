#!/usr/bin/env bash
# PreToolUse hook (Bash matcher) — git force push 직전 사용자 승인 프롬프트(ask).
# 정책: --force / -f / --force-with-lease 가 붙은 push 에서만 `permissionDecision="ask"` 로 승인을 요청한다.
#       일반 push 는 프롬프트 없이 통과 (`Bash(git *)` allow 권한으로 바로 실행).
#       Approve → Claude 가 본 세션에서 직접 push 실행, Deny → 호출 취소 (자동 재시도도 다시 ask 프롬프트 통과 필요).

set -euo pipefail

input=$(cat)
command=$(printf '%s' "$input" | python3 -c "import json,sys;print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || true)

if ! [[ "$command" =~ (^|[[:space:]\;])git([[:space:]]+-[Cc][[:space:]]+[^[:space:]]+)?[[:space:]]+push([[:space:]]|$) ]]; then
  exit 0
fi

# 일반 push 는 승인 없이 통과 — force 계열 옵션이 있을 때만 승인 요청한다.
force_note=""
if [[ "$command" =~ --force-with-lease ]]; then
  force_note="⚠️ --force-with-lease 감지 — 원격 변경 덮어쓰기 가능. 푸시 대상 브랜치 확인 필수."
elif [[ "$command" =~ --force|[[:space:]]-f([[:space:]]|$) ]]; then
  force_note="🛑 --force / -f 감지 — main/master 로의 force push 는 절대 금지. 다른 브랜치라도 협업자 변경 덮어쓸 수 있음."
else
  exit 0
fi

reason="🔔 git force push 승인 요청

명령: ${command}
${force_note}

승인 전 확인할 항목:
- 현재 브랜치 / 푸시 대상 remote/branch
- 푸시될 커밋 목록 (git log --oneline origin/<branch>..HEAD)
- force 사용 이유 (원격 히스토리 덮어쓰기 위험)

Approve → Claude 가 직접 실행, Deny → 호출 취소 (자동 재시도도 다시 본 프롬프트 통과)."

python3 -c "
import json, sys
print(json.dumps({
  'hookSpecificOutput': {
    'hookEventName': 'PreToolUse',
    'permissionDecision': 'ask',
    'permissionDecisionReason': sys.argv[1]
  }
}, ensure_ascii=False))
" "$reason"
exit 0
