#!/usr/bin/env bash
# PostToolUse hook (Edit|Write|MultiEdit) — TDD/TPM 분석 산출물 작성 시 자가 검수 리마인더.
# 파이프라인(/feature·/implement) 밖 단독 작성 시에도 검수가 걸리도록 nudge 한다. 차단 없음.
# PostToolUse plain stdout 은 Claude 가 못 보므로 additionalContext JSON 으로 주입한다.
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/global-hook-guard.sh"
project_owns_hook "$(basename "${BASH_SOURCE[0]}")" && exit 0

input=$(cat)
file=$(printf '%s' "$input" | python3 -c "import json,sys;d=json.load(sys.stdin).get('tool_input',{});print(d.get('file_path') or d.get('path',''))" 2>/dev/null || true)

case "$(basename "$file")" in
  tdd.md)
    msg="TDD 산출물을 작성했습니다. 사용자 승인 전 자가 검수를 권장합니다 — rules/tdd-review-criteria.md 기준으로 필수 섹션 누락·조건부 섹션(Observability·롤백·FE·Security) 필요성을 점검하거나, prd-reviewer 를 TDD 검수 모드로 호출하세요. (단독 작성 시 파이프라인 자동 검수가 걸리지 않습니다.)"
    ;;
  tpm-analysis.md)
    msg="TPM 분석 산출물을 작성했습니다. prd-reviewer 검수(요구사항 누락·티켓 분해·정책 충돌)를 아직 거치지 않았다면 호출을 권장합니다. (단독 작성 시 파이프라인 자동 검수가 걸리지 않습니다.)"
    ;;
  *) exit 0 ;;
esac

MSG="$msg" python3 -c "import json,os;print(json.dumps({'hookSpecificOutput':{'hookEventName':'PostToolUse','additionalContext':os.environ['MSG']}}))"
exit 0
