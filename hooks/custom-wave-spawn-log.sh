#!/usr/bin/env bash
# PreToolUse hook (Task|Agent matcher) — 서브에이전트 스폰 시각을 ledger 에 기록한다.
# 목적: wave 병렬/직렬 여부를 사후 감사(/wave-audit)하기 위한 자동 타임스탬프 수집. 차단 없음(항상 allow).
# 협조 불필요 — 오케스트레이터가 스폰할 때마다 자동 1줄 append.
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/global-hook-guard.sh"
project_owns_hook "$(basename "${BASH_SOURCE[0]}")" && exit 0

input=$(cat)
LEDGER_DIR="$HOME/.claude/.wave-ledger"
mkdir -p "$LEDGER_DIR" 2>/dev/null || true

INPUT="$input" LEDGER_DIR="$LEDGER_DIR" python3 - <<'PY' 2>/dev/null || true
import json, os, time
inp = json.loads(os.environ.get("INPUT") or "{}")
ti = inp.get("tool_input", {}) or {}
ts = time.time()
rec = {
    "ts": round(ts, 3),
    "tool": inp.get("tool_name", ""),
    "agent": ti.get("subagent_type", "") or "",
    "desc": ((ti.get("description") or "")[:80]),
}
day = time.strftime("%Y%m%d", time.localtime(ts))
path = os.path.join(os.environ["LEDGER_DIR"], day + ".jsonl")
with open(path, "a") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
PY
exit 0
