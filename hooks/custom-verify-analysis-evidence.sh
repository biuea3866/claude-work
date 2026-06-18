#!/usr/bin/env bash
# custom-verify-analysis-evidence.sh
# PreToolUse 백스톱 — 로컬 Datadog 에러 이슈 분석 루프가 Confluence에 기록할 때,
# 실제 검증 근거가 없으면 쓰기를 차단한다. "검증 없이 그럴듯한 가설만 기록" 방지.
#
# 차단 조건 (우리 분석 페이지에 한해):
#   - APM trace 링크도, Error Tracking issue 링크도 없음  → Datadog 미조회 의심
#   - 코드 file:line 참조가 없고, "코드 위치 미확인" 명시도 없음
#
# 대상이 아니거나(다른 Confluence 페이지/다른 도구) 파싱 실패 시 통과(안전 기본값).
set -euo pipefail
input="$(cat)"

verdict="$(printf '%s' "$input" | python3 -c '
import sys, json, re
try:
    d = json.load(sys.stdin)
except Exception:
    print("OK"); sys.exit(0)
name = d.get("tool_name", "") or ""
ti = d.get("tool_input", {}) or {}
body = ti.get("body", "") or ""
title = ti.get("title", "") or ""

if "ConfluencePage" not in name:
    print("OK"); sys.exit(0)

# 우리 분석 페이지만 대상 (제목 또는 본문 마커)
is_ours = (
    ("에러 이슈 분석" in title) or ("Regression 분석" in title)
    or ("로컬 Datadog 에러 이슈 분석 루프" in body)
    or ("로컬 Regression 분석 루프" in body)
)
if not is_ours:
    print("OK"); sys.exit(0)

has_dd = ("app.datadoghq.com/apm/trace/" in body) or ("app.datadoghq.com/error-tracking/issue/" in body)
has_code = re.search(r"[A-Za-z0-9_]+\.(kt|java|ts|sql|ya?ml):[0-9]+", body) is not None
ack_no_code = "코드 위치 미확인" in body

problems = []
if not has_dd:
    problems.append("Datadog 근거 링크 없음(APM trace 또는 Error Tracking issue URL 필수)")
if not has_code and not ack_no_code:
    problems.append("코드 file:line 참조 없음(또는 \"코드 위치 미확인\" 명시 필요)")

print("BLOCK::" + " / ".join(problems) if problems else "OK")
')"

case "$verdict" in
  BLOCK::*)
    echo "[분석 기록 차단] 검증 근거 부족 — ${verdict#BLOCK::}. 실제 Datadog 조회 결과(trace/issue 링크)와 코드 file:line을 포함해 재작성하세요. 검증 못 한 항목은 본문에 '❓미검증'으로 분리하고 검증 명령을 적으세요." >&2
    exit 2
    ;;
  *)
    exit 0
    ;;
esac
