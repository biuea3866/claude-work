#!/usr/bin/env bash
# 글로벌 hook 의 "로컬 우선 + 합집합" 가드.
#
# Claude Code 는 글로벌(~/.claude)·프로젝트(.claude) hook 을 가산 병합한다 — 둘 다 실행.
# 프로젝트가 자체 .claude/settings.json 에 동일 hook 을 이미 등록했다면, 글로벌 hook 은
# 비켜선다(no-op). 프로젝트가 등록하지 않은 hook 만 글로벌이 보강한다 → 로컬 우선 합집합.
#
# 글로벌 hook 스크립트가 상단에서 source 한 뒤 자기 basename 으로 호출한다:
#   source "$(dirname "${BASH_SOURCE[0]}")/lib/global-hook-guard.sh"
#   project_owns_hook "$(basename "${BASH_SOURCE[0]}")" && exit 0

# 현재 프로젝트(.claude/settings.json)가 이 hook 파일명을 등록했으면 0(true) 반환.
project_owns_hook() {
  local hook_name="$1"
  local proj="${CLAUDE_PROJECT_DIR:-}"
  [[ -z "$hook_name" ]] && return 1
  [[ -z "$proj" ]] && return 1
  local proj_settings="$proj/.claude/settings.json"
  [[ -f "$proj_settings" ]] || return 1
  grep -q "$hook_name" "$proj_settings"
}
