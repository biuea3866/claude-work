#!/usr/bin/env bash
# PostToolUse hook (Edit|Write|MultiEdit matcher) — .avsc/.avdl 편집 후 호환성 명시 리마인더.
# 차단 없음. Claude 컨텍스트에 system-reminder 로 주입한다.
#
# PostToolUse 의 plain stdout 은 debug log 에만 기록되고 Claude 가 보지 못한다
# (공식 문서: SessionStart/UserPromptSubmit/UserPromptExpansion 만 plain stdout → context 주입).
# 따라서 본 훅은 {"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"..."}}
# JSON 을 stdout 으로 내보내야 Claude 가 메시지를 읽고 후속 동작(호환성 명시/스킬 호출)을 한다.
#
# 본 워크스페이스에서 .avsc 는 .gitignore 로 추적 차단된 빌드 산출물 (IDL 컴파일 결과 또는
# Schema Registry 다운로드). 사람이 편집하는 SSOT 는 .avdl — 따라서 실제 트리거는 거의
# .avdl 편집 시점이다. .avsc 매처는 generated 디렉토리에서 손으로 들여다보는 케이스의 안전망.

set -euo pipefail

input=$(cat)
file=$(printf '%s' "$input" | python3 -c "import json,sys;d=json.load(sys.stdin).get('tool_input',{});print(d.get('file_path') or d.get('path',''))" 2>/dev/null || true)

case "$file" in
  *.avsc|*.avdl) ;;
  *) exit 0 ;;
esac

FILE="$file" python3 <<'PY'
import json, os
file = os.environ.get("FILE", "")
msg = f"""Avro 스키마가 변경되었습니다: {file}

⚠ 위치 점검: 본 모노레포의 .avsc/.avdl 은 .gitignore 로 추적 차단된 빌드 산출물 입니다.
   Avro 스키마의 실제 SSOT 는 외부 repo doodlincorp/greeting-topic/schemas/ 입니다.
   현재 변경이 빌드 산출물 (build/ 안의 generated) 이라면 커밋 대상 아닙니다.
   실제 정의 변경이라면 doodlincorp/greeting-topic 에 별도 PR 을 올리세요 (custom-infra-engineer 영역 2 참조).

다음을 명시해야 운영 사고를 막을 수 있습니다:

  1. 호환성 결정: BACKWARD / FORWARD / FULL / NONE 중 하나 + 근거
  2. 배포 순서: producer-first vs consumer-first 중 어느 쪽인지 + 이유
  3. 영향 받는 토픽 / consumer group / 다운스트림 모듈

검증 방법:
  - custom-avro-schema-reviewer 에이전트로 사전 리뷰 요청 (호환성 매트릭스 + producer/consumer 영향)
  - Schema Registry checkCompatibility 호출 (readonly)

위반 사례: 필수 필드 default 없이 추가 → 기존 consumer 가 못 읽음 (BACKWARD 위반)."""
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": msg,
    }
}))
PY

exit 0
