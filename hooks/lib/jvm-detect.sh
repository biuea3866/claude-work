#!/usr/bin/env bash
# 공용 JVM 탐지 — custom-gradlew-jvm-guard.sh / custom-session-start.sh 가 source 한다.
# 모듈 CLAUDE.md "## 스택 핀" 섹션의 JVM 핀 추출 + 현재 java 버전 추출을 한 곳에서 관리.

# 모듈 CLAUDE.md 의 "## 스택 핀" 섹션에서 요구 JVM major 버전 추출. 없으면 빈 문자열.
# 전체 파일 first-match 는 비교 설명용으로 다른 모듈 JVM 을 먼저 언급한 경우 오추출되므로
# 반드시 `## 스택 핀` ~ 다음 `## ` 사이만 본다.
jvm_required() {
  local claudemd="$1"
  [[ -f "$claudemd" ]] || { echo ""; return 0; }
  awk '/^## 스택 핀/{found=1; next} /^## /{if(found) exit} found' "$claudemd" \
    | grep -oE 'JVM[[:space:]]*\**[[:space:]]*([0-9]+)' | head -1 | grep -oE '[0-9]+' || true
}

# 현재 java major 버전 추출 ($JAVA_HOME 우선, fallback PATH). 추출 실패 시 빈 문자열.
jvm_current() {
  if [[ -n "${JAVA_HOME:-}" && -x "$JAVA_HOME/bin/java" ]]; then
    "$JAVA_HOME/bin/java" -version 2>&1 | head -1 | grep -oE '"[0-9]+' | tr -d '"' || true
  else
    java -version 2>&1 | head -1 | grep -oE '"[0-9]+' | tr -d '"' || true
  fi
}
