#!/usr/bin/env bash
# private-* hook 공용 스코핑 가드.
#
# private hook 은 "개인 프로젝트"에서만 동작한다. 개인 프로젝트 여부는 레포 루트의
# 마커 파일 `.claude/private-project` 존재로 판단한다 (명시적 opt-in).
#
# 마커는 레포에 커밋해 둔다 — 에이전트가 만드는 격리 worktree 체크아웃에도
# 마커가 존재해야 hook 이 worktree 안에서도 동작한다.
#
# 사용법 (hook 스크립트 상단):
#   source "$(dirname "${BASH_SOURCE[0]}")/lib/private-project-guard.sh"
#   is_private_project "$hint_path" || exit 0
#
# $hint_path: 판단 기준 경로 힌트 (파일 경로 또는 cwd). 비어 있으면
# CLAUDE_PROJECT_DIR → 현재 pwd 순으로 판단한다.

_has_marker() {
  [[ -n "$1" && -f "$1/.claude/private-project" ]]
}

# 주어진 경로에서 위로 올라가며 마커를 찾는다 (worktree·모노레포 대응, 최대 12단계).
_walk_up_for_marker() {
  local dir="$1"
  [[ -z "$dir" ]] && return 1
  [[ -f "$dir" ]] && dir="$(dirname "$dir")"
  local depth=0
  while [[ -n "$dir" && "$dir" != "/" && $depth -lt 12 ]]; do
    _has_marker "$dir" && return 0
    dir="$(dirname "$dir")"
    depth=$((depth + 1))
  done
  return 1
}

# 0(true) = 개인 프로젝트 → private hook 활성화
is_private_project() {
  local hint="${1:-}"

  # 1) CLAUDE_PROJECT_DIR (Claude Code 주입) 직접 확인
  if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then
    _has_marker "$CLAUDE_PROJECT_DIR" && return 0
  fi

  # 2) 힌트 경로(파일 경로·cwd)에서 위로 탐색 — worktree 는 CLAUDE_PROJECT_DIR 밖일 수 있다
  if [[ -n "$hint" ]]; then
    _walk_up_for_marker "$hint" && return 0
  fi

  # 3) 현재 작업 디렉토리 기준
  _walk_up_for_marker "$(pwd)" && return 0

  return 1
}
