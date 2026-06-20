#!/usr/bin/env bash
# PreToolUse hook (Task matcher) — 백그라운드 에이전트 스폰 시 isolation: "worktree" 강제.
#
# 문제: run_in_background: true 로 에이전트를 병렬 실행하면 동일 git 워크트리를 공유해
#       브랜치 전환 때 git stash 가 자동 발생하고 WIP 가 누적된다.
#
# 동작: run_in_background=true + isolation 미설정 → exit 2 차단.
#       Claude 가 에러를 읽고 isolation: "worktree" 를 추가해 재호출한다.
#
# 우회: description 또는 prompt 에 "# !read-only" 를 포함하면
#       파일을 쓰지 않는 에이전트로 간주해 통과 (Explore·리서치 에이전트 등).

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/global-hook-guard.sh"
project_owns_hook "$(basename "${BASH_SOURCE[0]}")" && exit 0

input=$(cat)

verdict=$(INPUT="$input" python3 - <<'PY'
import json, os, sys

try:
    d = json.loads(os.environ.get("INPUT") or "{}")
except Exception:
    print("OK"); sys.exit(0)

ti = d.get("tool_input", {}) or {}
is_background = bool(ti.get("run_in_background", False))
isolation = ti.get("isolation", "") or ""
prompt = ti.get("prompt", "") or ""
desc  = ti.get("description", "") or ""

if "# !read-only" in prompt or "# !read-only" in desc:
    print("OK"); sys.exit(0)

if is_background and isolation != "worktree":
    print("BLOCK")
else:
    print("OK")
PY
)

[[ "$verdict" == "OK" ]] && exit 0

cat >&2 <<'EOF'
🛑 백그라운드 에이전트에 isolation: "worktree" 가 누락됩니다.

run_in_background: true 로 에이전트를 병렬 실행하면 동일 git 워크트리를 공유해
브랜치 전환 시 git stash 가 자동 생성되고 WIP 가 누적됩니다.

수정: Agent 호출에 isolation: "worktree" 를 추가하세요.

  Agent({
    description: "...",
    prompt: "...",
    run_in_background: true,
    isolation: "worktree",   ← 반드시 추가
  })

읽기 전용 에이전트(파일 미수정)라면 description 또는 prompt 에
"# !read-only" 를 포함하면 이 가드를 통과합니다.
EOF
exit 2
