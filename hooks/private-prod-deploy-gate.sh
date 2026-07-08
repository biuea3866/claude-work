#!/usr/bin/env bash
# PreToolUse hook (Bash matcher) — [개인 프로젝트 전용] prod 배포 게이트 (QA PASS 강제).
# 기준: rules/private-deploy-convention.md — prod 배포는 private-qa verdict PASS 가 선행돼야 한다.
#
# 식별: docker compose 명령이 `up`/`run` 을 포함하고 prod 지시자(-f *prod* 파일 / --profile prod)가 있으면 prod 배포.
# 정책: `# qa-passed` 토큰이 없으면 exit 2 로 차단한다.
#       → private-qa 실행 → verdict PASS 확인 → 토큰을 붙여 재호출하면 통과 (감사 대상).
# 스코핑: 레포 루트 마커 `.claude/private-project` 가 있는 개인 프로젝트에서만 동작.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/global-hook-guard.sh"
project_owns_hook "$(basename "${BASH_SOURCE[0]}")" && exit 0
source "$(dirname "${BASH_SOURCE[0]}")/lib/private-project-guard.sh"

input=$(cat)
command=$(printf '%s' "$input" | python3 -c "import json,sys;print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || true)
hook_cwd=$(printf '%s' "$input" | python3 -c "import json,sys;print(json.load(sys.stdin).get('cwd',''))" 2>/dev/null || true)

[[ -z "$command" ]] && exit 0
is_private_project "$hook_cwd" || exit 0

# docker compose (또는 docker-compose) 명령만 대상
[[ "$command" =~ (^|[[:space:]\;\&\|])docker([[:space:]]+compose|-compose)([[:space:]]|$) ]] || exit 0

# 배포 동작(up / run)이 아니면 통과 (ps, logs, down, config 등)
[[ "$command" =~ [[:space:]](up|run)([[:space:]]|$) ]] || exit 0

# prod 지시자: -f <*prod*> 파일 또는 --profile prod
is_prod=0
if [[ "$command" =~ -f[[:space:]]+[^[:space:]]*prod[^[:space:]]* ]]; then
  is_prod=1
elif [[ "$command" =~ --profile[[:space:]=]+prod([[:space:]]|$) ]]; then
  is_prod=1
fi
[[ $is_prod -eq 0 ]] && exit 0

# 우회 토큰: private-qa verdict PASS 확인 후 명시 (감사 대상)
[[ "$command" == *"qa-passed"* ]] && exit 0

cat >&2 <<'EOF'
🛑 [private] prod 배포 차단 — QA 통과 확인이 선행되지 않았습니다.

prod 배포 조건 (rules/private-deploy-convention.md):
  1) private-qa 에이전트 실행 — dev 실구동 E2E(신규 시나리오 + 회귀 카탈로그 전체)
  2) verdict PASS 확인 (blocker/major 0건, QA 리포트 저장 완료)
  3) 배포 명령 끝에 토큰을 붙여 재호출:
     docker compose -f docker-compose.prod.yml up -d   # qa-passed

- prod 이미지 태그는 latest 금지 — git SHA/기능명 태그 고정 (롤백 = 직전 태그 재기동).
- QA PASS 없이 토큰만 붙이는 것은 거짓 단언(COMPLETION-RULE 위반)입니다. 감사 대상.
EOF
exit 2
