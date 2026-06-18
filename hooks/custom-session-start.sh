#!/usr/bin/env bash
# SessionStart hook — 현재 작업 디렉토리 기반으로 모듈/JDK/시크릿 상태를 1회 안내.
# stdout은 Claude 세션 컨텍스트에 주입된다.

set -euo pipefail

# Claude Code 가 SessionStart hook 에 stdin JSON 을 보낸다. cwd 필드 포함.
# 직접 호출 시 stdin 이 비어 있을 수 있으므로 양쪽 fallback 유지.
input=$(cat 2>/dev/null || true)

# ROOT 결정: Claude Code 가 주입하는 CLAUDE_PROJECT_DIR 우선.
# 직접 호출 시 fallback 은 스크립트 위치(.claude/hooks/) 기준 두 단계 위로 역산.
if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then
  ROOT="$CLAUDE_PROJECT_DIR"
else
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi

# CWD 결정: hook stdin JSON 의 cwd 우선, 없으면 process pwd.
# Claude Code 가 모듈 디렉토리 안에서 세션을 시작한 경우 stdin.cwd 가 그 경로다 — pwd 는 hook 실행 컨텍스트에 따라 달라질 수 있어 stdin 값이 더 정확.
cwd_parse_err=""
if command -v python3 >/dev/null 2>&1; then
  CWD=$(printf '%s' "$input" | python3 -c "import json,sys;d=json.loads(sys.stdin.read() or '{}');print(d.get('cwd',''))" 2>&1) || cwd_parse_err="python3 parse failed: $CWD"
else
  cwd_parse_err="python3 not found in PATH"
  CWD=""
fi
if [[ -z "$CWD" || -n "$cwd_parse_err" ]]; then
  CWD="$(pwd)"
  [[ -n "$cwd_parse_err" ]] && echo "ℹ hook stdin parse fallback → pwd 사용 ($cwd_parse_err)"
fi

# 1) 현재 cwd가 모노레포 루트에서 어떤 모듈인지 식별
relpath="${CWD#"$ROOT"/}"
module="${relpath%%/*}"

echo "=== Greeting Workspace Harness ==="
echo "cwd:    $CWD"

if [[ "$CWD" == "$ROOT" ]]; then
  echo "module: (root) — Gradle 빌드를 직접 실행하지 마세요. 모듈 디렉토리로 cd 후 ./gradlew를 사용하세요."
elif [[ -f "$ROOT/$module/CLAUDE.md" ]]; then
  echo "module: $module"
  # 2) 모듈 CLAUDE.md의 "## 스택 핀" 섹션 내부에서만 JVM 버전 추출.
  #    전체 파일 first-match 는 비교 설명용으로 다른 모듈 JVM 을 먼저 언급한 경우(예: doodlin-communication 본문이
  #    greeting-communication 의 JVM 21 을 먼저 인용)에 오추출된다. custom-gradlew-jvm-guard.sh 와 동일 규칙.
  jvm=$(awk '/^## 스택 핀/{found=1; next} /^## /{if(found) exit} found' "$ROOT/$module/CLAUDE.md" \
    | grep -oE 'JVM[[:space:]]*\**[[:space:]]*([0-9]+)' | head -1 | grep -oE '[0-9]+' || true)
  if [[ -n "${jvm:-}" ]]; then
    echo "required JVM: $jvm  (export JAVA_HOME=\$(/usr/libexec/java_home -v $jvm))"
    # JVM 판정은 custom-gradlew-jvm-guard.sh 와 동일한 우선순위 — $JAVA_HOME 우선, fallback PATH
    if [[ -n "${JAVA_HOME:-}" && -x "$JAVA_HOME/bin/java" ]]; then
      current_jvm=$("$JAVA_HOME/bin/java" -version 2>&1 | head -1 | grep -oE '"[0-9]+' | tr -d '"' || echo "?")
    else
      current_jvm=$(java -version 2>&1 | head -1 | grep -oE '"[0-9]+' | tr -d '"' || echo "?")
    fi
    if [[ "$current_jvm" == "?" || -z "$current_jvm" ]]; then
      echo "ℹ 현재 JVM 추출 실패 — java/JAVA_HOME 미설정 가능. \`export JAVA_HOME=\$(/usr/libexec/java_home -v $jvm)\` 후 재시도."
    elif [[ "$current_jvm" != "$jvm" ]]; then
      echo "⚠ JVM 미스매치: 현재=$current_jvm, 모듈 요구=$jvm (gradle guard 와 동일한 \$JAVA_HOME 우선)"
    fi
  else
    echo "ℹ 모듈 $module 의 CLAUDE.md 에서 '## 스택 핀' 섹션 JVM 추출 실패 — gradle guard 가 비활성. CLAUDE.md 형식 점검 필요 (예: 'JVM 17' 형태 라인이 섹션 안에 있는가)."
  fi
else
  echo "module: (unknown - $module)"
fi

# 3) 필수 환경 변수 점검 (GH Packages 인증 불필요 모듈은 제외)
no_gh_modules=("greeting-shiftee-worker" "greeting_mail-template-server" "offercent-search")
needs_gh=true
for m in "${no_gh_modules[@]}"; do
  [[ "$module" == "$m" ]] && needs_gh=false && break
done

if $needs_gh; then
  [[ -z "${GITHUB_USERNAME:-}" ]] && echo "✗ GITHUB_USERNAME 미설정 — GH Packages 의존 해결 실패 예상"
  [[ -z "${GITHUB_TOKEN:-}"    ]] && echo "✗ GITHUB_TOKEN 미설정 — read:packages 스코프 PAT 필요"
fi

# 4) Avro/SR 모듈 안내
avro_modules=("greeting-ats" "greeting-new-back" "greeting-workspace-server" "greeting-aggregator" "integration")
for m in "${avro_modules[@]}"; do
  if [[ "$module" == "$m" ]]; then
    [[ -z "${CONFLUENT_CLOUD_SCHEMA_REGISTRY_URL:-}${CONFLUENT_CLOUD_SCHEMA_REGISTRY_HOST:-}" ]] \
      && echo "ℹ Avro/SR 모듈입니다. 통합 빌드 시 CONFLUENT_CLOUD_SCHEMA_REGISTRY_* 환경 변수 필요."
    break
  fi
done

# 5) .mcp.json preflight — required env 가 unset 이면 Claude Code 의 ${VAR} 확장이 실패해
#    MCP 서버 자체가 기동 안 되거나(파싱 실패) 빈 인자로 떠 도구 호출이 실패한다.
#    구체 실패 모드는 Claude Code 버전마다 다를 수 있으니 진단은 "조회 불가" 수준으로만 남긴다.
#    onboarding.md Step 3 의 export 누락을 세션 진입 시점에 잡는 게 목적.
if [[ -z "${CONTEXT7_API_KEY:-}" ]]; then
  echo "✗ CONTEXT7_API_KEY 미설정 — context7 MCP 도구 호출이 실패할 수 있음 (라이브러리 도큐먼트 조회 불가)."
fi
if [[ -z "${GRAFANA_SERVICE_ACCOUNT_TOKEN:-}" ]]; then
  echo "✗ GRAFANA_SERVICE_ACCOUNT_TOKEN 미설정 — grafana-dev MCP 도구 호출이 실패할 수 있음. monitoring.dev.greetinghr.com 에서 토큰 발급."
fi

echo "harness: .claude/HARNESS.md 참조 — custom-module-router 스킬로 라우팅, agents/* 로 위임"
echo "=================================="

# 6) LLM 협업 가이드라인 본문 echo — 이전에는 CLAUDE.md `@import` 로 적용했으나, 카파시 가이드 원본 의도(매 세션 강한 reminder)에 맞춰 SessionStart hook 으로 주입한다.
guideline="$ROOT/.claude/guidelines/llm-collaboration.md"
if [[ -f "$guideline" ]]; then
  echo ""
  echo "=== LLM 협업 가이드라인 (매 세션 reminder) ==="
  cat "$guideline"
  echo "============================================="
else
  echo "✗ LLM 협업 가이드라인 파일 누락 — 본 hook 의 핵심 페이로드가 주입되지 않습니다."
  echo "  expected: $guideline"
  echo "  복구: git checkout origin/dev -- .claude/guidelines/llm-collaboration.md"
fi
