#!/usr/bin/env bash
# PreToolUse hook (Bash matcher) — [개인 프로젝트 전용] 파괴적 명령 차단.
# 대상: Redis FLUSHALL/FLUSHDB, SQL DROP/TRUNCATE, Kafka 토픽 삭제, git push --force.
# 각 컨벤션(private-redis/kafka/db-schema-convention)의 "파괴적 변경은 실행 전 사용자 확인 필수" 강제 장치.
#
# 정책: 우회 토큰 `# destructive-confirmed` 가 없으면 exit 2 로 차단한다.
#       → 사용자에게 확인받은 후 명령 끝에 토큰을 붙여 재호출하면 통과 (감사 대상).
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

# 우회 토큰: 사용자 확인 완료 후 명령에 명시 (감사 대상)
[[ "$command" == *"destructive-confirmed"* ]] && exit 0

matched=""

shopt -s nocasematch
if [[ "$command" =~ FLUSHALL|FLUSHDB ]]; then
  matched="Redis FLUSH — 전체/DB 키 삭제"
elif [[ "$command" =~ DROP[[:space:]]+(TABLE|DATABASE|SCHEMA) ]]; then
  matched="SQL DROP — 테이블/데이터베이스 삭제"
elif [[ "$command" =~ TRUNCATE[[:space:]]+(TABLE[[:space:]]+)?[a-z_\`\"] ]]; then
  matched="SQL TRUNCATE — 데이터 전체 삭제"
elif [[ "$command" =~ kafka-topics ]] && [[ "$command" =~ --delete ]]; then
  matched="Kafka 토픽 삭제"
elif [[ "$command" =~ dropDatabase ]]; then
  matched="MongoDB dropDatabase — 데이터베이스 삭제"
elif [[ "$command" =~ \.drop\(\) ]]; then
  matched="MongoDB 컬렉션 drop"
elif [[ "$command" =~ deleteMany\(\{\}\) ]]; then
  matched="MongoDB deleteMany({}) — 컬렉션 전체 삭제"
fi
shopt -u nocasematch

if [[ -z "$matched" ]] && [[ "$command" =~ git[[:space:]].*push ]]; then
  if [[ "$command" =~ --force([[:space:]]|$) || "$command" =~ [[:space:]]-f([[:space:]]|$) ]]; then
    matched="git push --force — 원격 히스토리 덮어쓰기 (--force-with-lease 우선 검토)"
  fi
fi

[[ -z "$matched" ]] && exit 0

cat >&2 <<EOF
🛑 [private] 파괴적 명령 차단 — $matched

명령: $command

개인 컨벤션(private-redis/kafka/db-schema-convention)에 따라 파괴적 변경은
실행 전 사용자 확인이 필수입니다.

1) 사용자에게 대상·영향 범위·복구 방법을 보고하고 확인을 받으세요.
2) 확인 후 명령 끝에 우회 토큰을 붙여 재호출하세요:
   <명령>   # destructive-confirmed
EOF
exit 2
