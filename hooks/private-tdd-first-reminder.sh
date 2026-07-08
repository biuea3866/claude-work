#!/usr/bin/env bash
# PostToolUse hook (Edit|Write|MultiEdit matcher) — [개인 프로젝트 전용] TDD 테스트-퍼스트 리마인더.
# 프로덕션 소스를 작성/수정했는데 대응 테스트 파일이 보이지 않으면 경고를 컨텍스트에 주입한다.
# 차단 없음 (휴리스틱 한계) — 최종 방어는 private-code-reviewer(테스트 누락 p2)가 담당.
#
# 판정:
#   Kotlin — src/main/**/Foo.kt 수정 시 같은 모듈 src/test 아래 Foo*(Test|Spec).kt 존재 여부
#   TS/TSX — src/**/foo.tsx 수정 시 foo.test.* / __tests__/foo.* 존재 여부
# 스코핑: 레포 루트 마커 `.claude/private-project` 가 있는 개인 프로젝트에서만 동작.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/global-hook-guard.sh"
project_owns_hook "$(basename "${BASH_SOURCE[0]}")" && exit 0
source "$(dirname "${BASH_SOURCE[0]}")/lib/private-project-guard.sh"

input=$(cat)
file=$(printf '%s' "$input" | python3 -c "import json,sys;d=json.load(sys.stdin).get('tool_input',{});print(d.get('file_path') or d.get('path',''))" 2>/dev/null || true)

[[ -z "$file" ]] && exit 0
is_private_project "$file" || exit 0

missing=""

case "$file" in
  */src/main/*.kt)
    stem="$(basename "$file" .kt)"
    module_root="${file%%/src/main/*}"
    if [[ -d "$module_root/src/test" ]]; then
      found=$(find "$module_root/src/test" -type f \( -name "${stem}Test.kt" -o -name "${stem}Spec.kt" -o -name "${stem}*Test.kt" \) 2>/dev/null | head -1)
    else
      found=""
    fi
    [[ -z "$found" ]] && missing="kotlin"
    ;;
  *.test.ts|*.test.tsx|*.spec.ts|*.spec.tsx) exit 0 ;;
  */__tests__/*) exit 0 ;;
  */src/*.ts|*/src/*.tsx)
    base="$(basename "$file")"
    stem="${base%.*}"
    dir="$(dirname "$file")"
    found=$(find "$dir" -maxdepth 2 -type f \( -name "${stem}.test.*" -o -name "${stem}.spec.*" -o -path "*__tests__/${stem}.*" \) 2>/dev/null | head -1)
    # 타입 정의·설정·엔트리 파일은 제외
    case "$base" in
      *.d.ts|index.ts|index.tsx|types.ts|*.config.*) exit 0 ;;
    esac
    [[ -z "$found" ]] && missing="ts"
    ;;
  *) exit 0 ;;
esac

[[ -z "$missing" ]] && exit 0

FILE="$file" python3 <<'PY'
import json, os
file = os.environ.get("FILE", "")
msg = f"""[private/TDD] 프로덕션 소스가 변경됐는데 대응 테스트 파일이 보이지 않습니다: {file}

전역 지침 §1 (TDD 우선) — 프로덕션 코드 한 줄보다 그 코드를 강제하는 실패하는 테스트가 먼저 존재해야 합니다.
지금 구현부터 쓰고 있다면 즉시 멈추고:
  1) RED — 실패하는 테스트를 먼저 작성하고 실행해 실패 확인 (Kotlin: Kotest / FE: Testing Library)
  2) GREEN — 통과시키는 최소 구현
  3) REFACTOR — 통과 상태에서 정리

이미 테스트가 다른 이름/경로에 있다면 이 알림은 무시해도 됩니다 (휴리스틱 탐지).
최종 검증은 private-code-reviewer 가 수행합니다 (테스트 누락 = p2 REQUEST_CHANGES)."""
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": msg,
    }
}))
PY

exit 0
