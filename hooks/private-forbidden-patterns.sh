#!/usr/bin/env bash
# PreToolUse hook (Edit|Write|MultiEdit matcher) — [개인 프로젝트 전용] 금지 패턴 차단.
# 개인 프로젝트에는 harness-rules.json 이 없으므로 이 hook 이 기계적 방어선이다.
# 기준: rules/private-be-code-convention.md · rules/private-fe-convention.md 의 금지 패턴 표.
#
# 정책: 작성/수정하려는 내용에 금지 패턴이 있으면 exit 2 로 차단하고 대체 패턴을 안내한다.
#       정당한 예외는 해당 라인에 `private-allow:<rule-id>` 주석을 붙이면 통과한다 (감사 대상).
# 스코핑: 레포 루트 마커 `.claude/private-project` 가 있는 개인 프로젝트에서만 동작.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/global-hook-guard.sh"
project_owns_hook "$(basename "${BASH_SOURCE[0]}")" && exit 0
source "$(dirname "${BASH_SOURCE[0]}")/lib/private-project-guard.sh"

input=$(cat)

file=$(printf '%s' "$input" | python3 -c "import json,sys;d=json.load(sys.stdin).get('tool_input',{});print(d.get('file_path') or d.get('path',''))" 2>/dev/null || true)
[[ -z "$file" ]] && exit 0

is_private_project "$file" || exit 0

# 검사 본체는 lib/private-forbidden-patterns.py (heredoc 은 파이프 stdin 을 덮어쓰므로 파일로 분리)
printf '%s' "$input" | python3 "$(dirname "${BASH_SOURCE[0]}")/lib/private-forbidden-patterns.py"
exit $?
