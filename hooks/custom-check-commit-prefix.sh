#!/usr/bin/env bash
# PreToolUse hook (Bash matcher) — git commit 메시지에 GRT-/BE-/LIVEISSUE- 접두사 없으면 차단.
# `--no-jira` 의도 커밋은 메시지에 `no-jira` 문자열을 명시하면 통과.
#
# 메시지 모드 탐지는 shlex 기반:
#   - `-m foo` / `-m"foo"` (붙임) / `-mfoo` (붙임) / `-am "..."` (short cluster) / `--message foo` / `--message=foo`
#   - 모두 message 모드로 분류. 이전 grep 기반은 `-am` / `-mfix` / `-m"..."` 가 boundary 부재로 통과했음.
# `-F file` / editor 모드는 pre-commit-msg git hook + PR title CI 가 사후 가드.

set -euo pipefail

input=$(cat)
command=$(printf '%s' "$input" | python3 -c "import json,sys;print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || true)

[[ -z "$command" ]] && exit 0

verdict=$(COMMAND="$command" python3 - <<'PY' 2>/dev/null || echo "OK"
import os, re, shlex, sys

cmd = os.environ.get("COMMAND", "")
if not cmd:
    print("OK"); sys.exit(0)

# 명시적 no-jira 우회 (예: "no-jira: docs only")
if "no-jira" in cmd:
    print("OK"); sys.exit(0)

try:
    toks = shlex.split(cmd, posix=True)
except ValueError:
    toks = cmd.split()

# 'git commit' 위치 찾기. `git -C <dir> commit` / `git -c key=val commit` 도 허용.
commit_at = -1
i = 0
while i < len(toks):
    if toks[i] == "git":
        j = i + 1
        while j < len(toks) and toks[j] in ("-C", "-c") and j + 1 < len(toks):
            j += 2
        if j < len(toks) and toks[j] == "commit":
            commit_at = j
            break
    i += 1

if commit_at < 0:
    print("OK"); sys.exit(0)

# commit 이후 토큰 중 message 모드 탐지:
#   - short cluster (-[a-zA-Z]*m...) : -m / -am / -mfix / -m"foo" (붙임 후 shlex 가 -mfoo 형태로 토큰화)
#   - long (--message / --message=...)
short_m = re.compile(r"^-[a-zA-Z]*m")
long_m  = re.compile(r"^--message(=|$)")
msg_mode = any(short_m.match(t) or long_m.match(t) for t in toks[commit_at + 1:])
if not msg_mode:
    # -F file 또는 editor 모드 — pre-commit-msg / PR title CI 가 검증
    print("OK"); sys.exit(0)

# 전체 command 에서 prefix 검색 (heredoc / quote 변형 친화)
if re.search(r"\[(GRT|BE|LIVEISSUE)-[0-9]+\]", cmd):
    print("OK"); sys.exit(0)

print("BLOCK")
PY
)

if [[ "$verdict" != "BLOCK" ]]; then
  exit 0
fi

cat >&2 <<EOF
🛑 커밋 메시지 prefix 누락.

명령: $command

요구 형식 중 하나:
  [GRT-7565] - fix: 짧은 요약
  [BE-1234] - refactor: ...
  [LIVEISSUE-99] - fix: ...

- check_pr_title.yml 이 PR 단계에서 동일 검증을 강제합니다.
- JIRA 티켓 없는 작업은 메시지에 'no-jira' 명시 (예: "no-jira: docs only").
EOF
exit 2
