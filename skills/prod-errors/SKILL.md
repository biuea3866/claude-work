---
name: prod-errors
description: Datadog API로 프로덕션 에러를 조회한다. 서비스명 + 키워드 + 시간범위를 받으면 에러 이슈·로그·trace를 요약한다. env:prod 고정.
model: opus
user-invocable: true
---

조회 대상: $ARGUMENTS  (형식: `<서비스명> [키워드] [last 1h|last 24h|YYYY-MM-DDTHH:MM~HH:MM]`)

환경: `env:prod` 고정 — dev 에러 조회는 `/dev-errors` 사용

키: `$DD_API_KEY`, `$DD_APP_KEY`, `$DD_SITE`(=datadoghq.com) — `~/.zshrc`에서 로드. **키 값 출력 금지**.

---

**서비스명이 없으면 즉시 되묻는다.** 전역 조회 금지 (쿼터 소진).

시간 미지정 시 `last 1h` 적용. 절대시간은 ISO8601, 상대는 `now-1h`.

### 1. Error Tracking 이슈 조회

```bash
curl -sS -X POST "https://api.${DD_SITE}/api/v2/error-tracking/events/search" \
  -H "DD-API-KEY: ${DD_API_KEY}" -H "DD-APPLICATION-KEY: ${DD_APP_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"filter":{"query":"service:<svc> env:prod <keyword>","from":"<from>","to":"<to>"},"page":{"limit":20},"sort":"-timestamp"}'
```

추출: `issue.id`, `error.type`, `error.message`, 발생 횟수, 첫/마지막 시각, 스택 첫 프레임

### 2. 로그 조회

```bash
curl -sS -X POST "https://api.${DD_SITE}/api/v2/logs/events/search" \
  -H "DD-API-KEY: ${DD_API_KEY}" -H "DD-APPLICATION-KEY: ${DD_APP_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"filter":{"query":"service:<svc> status:error env:prod <keyword>","from":"<from>","to":"<to>"},"page":{"limit":50},"sort":"-timestamp"}'
```

추출: `timestamp`, `trace_id`, `message`, `error.message`, `error.stack`, `http.url`, `http.status_code`

### 3. 출력 형식

```
## Prod 에러 요약 (service=<s>, range=<from>~<to>)

### 이슈 TOP N
1. [ISSUE-XXX] <error.type>: <error.message>  N회 / 마지막 <ts>
   스택: <file>:<line>

### 추정 원인
- (스택 + 로그 기반 1~3줄)

### 영향 범위
- hosts: N / endpoints: top3

### 코드 위치
- <repo>/<path>:<line>  → /explore 또는 직접 Read로 확인

Datadog 링크: https://app.datadoghq.com/logs?query=service:<svc>+env:prod&...
```

raw JSON 전체 덤프 금지. 필요한 필드만 요약.
