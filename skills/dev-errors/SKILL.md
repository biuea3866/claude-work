---
name: dev-errors
description: Grafana Loki/Explore API로 dev 환경 에러를 조회한다. 서비스명 + 키워드 + 시간범위를 받으면 에러 로그를 요약한다. env:dev 고정.
model: opus
user-invocable: true
---

조회 대상: $ARGUMENTS  (형식: `<서비스명> [키워드] [last 1h|last 3h|YYYY-MM-DDTHH:MM~HH:MM]`)

환경: `env:dev` 고정 — 프로덕션 에러 조회는 `/prod-errors` 사용

URL: `https://monitoring.dev.greetinghr.com`
키: `$GRAFANA_TOKEN` — `~/.zshrc`에 세팅 필요. **값 출력 금지**.
없으면 즉시 중단하고 사용자에게 알린다.

---

**서비스명이 없으면 즉시 되묻는다.**

시간 미지정 시 `last 1h`. Unix 나노초(ns) 기준: `from=now-1h`, `to=now`.

### 1. Loki 로그 조회 (LogQL)

```bash
# URL 인코딩된 query 파라미터로 전달
QUERY='{namespace="greeting-dev",app="<svc>"} |= "error" |= "<keyword>" | logfmt | line_format "{{.ts}} {{.level}} {{.msg}}"'

curl -sS -G "https://monitoring.dev.greetinghr.com/loki/api/v1/query_range" \
  -H "Authorization: Bearer ${GRAFANA_TOKEN}" \
  --data-urlencode "query=${QUERY}" \
  --data-urlencode "start=$(date -v-1H +%s)000000000" \
  --data-urlencode "end=$(date +%s)000000000" \
  --data-urlencode "limit=100" \
  --data-urlencode "direction=backward"
```

추출: `stream` 레이블(app, pod, namespace), `values[][1]` 로그 라인

### 2. 스택트레이스 연속 로그 수집

에러 메시지 발견 시 전후 10줄 컨텍스트:
```bash
# 같은 pod에서 같은 timestamp 근처 로그
{namespace="greeting-dev",app="<svc>",pod="<pod>"} |= "<error_class>"
```

### 3. 출력 형식

```
## Dev 에러 요약 (service=<s>, range=<from>~<to>)

### 에러 TOP N
1. <error.class>: <error.message>  N회 / 마지막 <ts>
   pod: <pod-name>
   스택 첫 프레임: <file>:<line>

### 추정 원인
- (로그 기반 1~3줄)

### 재현 힌트
- 발생 직전 로그: (있으면)
- 관련 API 요청: (있으면)

### 코드 위치
- <repo>/<path>:<line>

Grafana 링크: https://monitoring.dev.greetinghr.com/explore?datasource=loki&query=...
```

raw JSON 전체 덤프 금지. `level=error` 이상만 추출.
dev 환경이므로 장애 심각도 판단 없이 원인 파악에만 집중.
