---
description: CS 문의 Slack 스레드 URL을 받아 문의 내용을 파악하고, Datadog 에러 로그와 코드 경로를 병렬로 추적해 원인을 종합한다.
---

# /cs-investigate — CS 문의 조사 파이프라인

## 입력
`$ARGUMENTS` — `<Slack스레드URL> [서비스명 override] [last 1h|last 24h|YYYY-MM-DDTHH:MM~HH:MM]`

키: `$DD_API_KEY`, `$DD_APP_KEY`, `$DD_SITE`(=datadoghq.com) — `~/.zshrc`에서 로드. **키 값 출력 금지**.

---

## 파이프라인 개요

```
Slack 스레드 URL
    │
    ▼
[Phase 1] 문의 내용 파악
    │ Slack MCP로 스레드 전체 읽기
    │ 문의 내용 / 발생 시각 / 서비스 힌트 / 에러 키워드 추출
    │ 서비스 미확인 시 → 즉시 되묻기 (전역 조회 금지)
    ▼
[Phase 2] 서비스·시간 확정
    │ 도메인 매핑으로 Datadog service명 결정
    │ 발생 시각 기준 ±1h 적용 (미지정 시)
    ▼
[Phase 3] 병렬 조회
    ├── 3-A: Datadog 에러 이슈 + 로그 조회
    └── 3-B: 코드 경로 탐색 (스택 → 파일 → 메서드)
    ▼
[Phase 4] 종합 보고
    │ 문의 맥락 + 에러 TOP N + 코드 레이어 + 추정 원인
    ▼
[Phase 5] 상담사 대응 보고서
    │ Phase 4 기반으로 상담사가 고객에게 안내할 수 있는 쉬운 설명 생성
    │ 원인 유형 분류 (시스템 버그 / 고객 실수 / 데이터 이슈 / 정상 동작)
    │ 상담사 행동 지침 (안내 문구 / 개발팀 에스컬레이션 여부 / 임시 우회 방법)
```

---

## Phase 1 — Slack 스레드 파악

Slack URL에서 channel_id와 message_ts를 추출해 MCP로 스레드 전체를 읽는다.

- URL 형식: `https://doodlin-corp.slack.com/archives/<channel_id>/p<ts_without_dot>`
- `p1778658096498009` → message_ts = `1778658096.498009`

추출 항목:

| 항목 | 추출 방법 |
|------|----------|
| 문의 내용 | 사용자가 겪은 현상·오류 메시지·재현 단계 |
| 발생 시각 | 메시지 timestamp 또는 본문의 명시적 시각 |
| 서비스 힌트 | 언급된 화면/API/기능명 → Phase 2 도메인 매핑으로 결정 |
| 에러 키워드 | 오류 코드, 화면 메시지, 예외 타입 등 |

**서비스를 결정할 수 없으면 즉시 되묻는다.** 전역 조회 금지.

---

## Phase 2 — 서비스·시간 확정

- `서비스명 override` 인수가 있으면 그것을 사용
- 없으면 Phase 1 힌트 + 도메인 매핑으로 결정
- 시간 미지정 시: 스레드 발생 시각 기준 `±1h` 적용

### 도메인 → 서비스명 매핑

| 도메인/화면 | Datadog service | 레포 |
|------------|-----------------|------|
| 지원자·공고·평가·파이프라인 | `greeting` | `greeting/greeting-new-back` |
| 오케스트레이션·집계 | `greeting-aggregator` | `greeting/greeting-aggregator` |
| 워크스페이스 | `greeting-workspace` | `greeting-workspace-server` |
| 결제·구독·플랜 | `greeting-payment` | `greeting_payment-server` |
| 인증 (로그인·SSO) | `greeting-authn` | `greeting_authn-server` |
| 인가 (권한) | `greeting-authz` | `greeting_authz-server` |
| 메일·알림톡·문자 | `greeting-communication` | `greeting-communication` |
| 대시보드 | `greeting-dashboard` | `greeting_dashboard-back` |
| TRM | `greeting-trm` | `greeting_trm-server` |
| 채용 페이지 | `greeting-career` | `greeting_career-next` |

---

## Phase 3 — 병렬 조회

**3-A와 3-B를 동시에 실행한다.**

### 3-A. 운영 에러 로그 조회

> **`skills/prod-errors/SKILL.md` 의 조회 절차를 그대로 따른다.** 서비스명·키워드·시간 범위가 확정된 상태이므로 되묻지 않고 바로 실행한다.

**에러 이슈 조회** (Error Tracking):

```bash
source ~/.zshrc 2>/dev/null
curl -sS -X POST "https://api.${DD_SITE}/api/v2/error-tracking/events/search" \
  -H "DD-API-KEY: ${DD_API_KEY}" -H "DD-APPLICATION-KEY: ${DD_APP_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {
      "query": "service:<svc> env:prod <keyword>",
      "from": "<from>",
      "to": "<to>"
    },
    "page": {"limit": 20},
    "sort": "-timestamp"
  }'
```

추출: `issue.id`, `error.type`, `error.message`, 발생 횟수, 첫/마지막 시각, 스택 첫 프레임

**로그 조회**:

```bash
source ~/.zshrc 2>/dev/null
curl -sS -X POST "https://api.${DD_SITE}/api/v2/logs/events/search" \
  -H "DD-API-KEY: ${DD_API_KEY}" -H "DD-APPLICATION-KEY: ${DD_APP_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {
      "query": "service:<svc> status:error env:prod <keyword>",
      "from": "<from>",
      "to": "<to>"
    },
    "page": {"limit": 50},
    "sort": "-timestamp"
  }'
```

추출: `timestamp`, `trace_id`, `message`, `error.message`, `error.stack`, `http.url`, `http.status_code`

에러·로그가 없으면 `status:warn`으로 재조회한다.

### 3-B. 코드 경로 탐색

> **`skills/explore/SKILL.md` 의 탐색 접근 순서를 따른다.** `.architecture/` 스냅샷을 우선 참조하고, 없으면 직접 코드를 grep한다.

스택 트레이스 또는 에러 키워드로 실제 코드를 추적한다.

1. **스냅샷 우선** — `.architecture/<repo>/api-map.md`, `domain-map.md`를 grep으로 키워드 검색
   ```bash
   grep -n "<키워드>" .architecture/<repo>/api-map.md | head -20
   grep -n "<키워드>" .architecture/<repo>/domain-map.md | grep -i "facade\|service\|port" | head -40
   ```
   > `greeting-new-back/domain-map.md` 32K 초과 — 반드시 grep 필터 후 읽기
2. **레이어 순서로 추적** — Controller → UseCase/Facade → DomainService → Entity ← Repository
3. **스택 프레임 직접 grep** — 스냅샷으로 좁힌 후 실제 파일에서 Grep으로 클래스·메서드 위치 확인
4. **코드 확인** — Read로 해당 메서드 ±20줄 읽기

---

## Phase 4 — 종합 보고

```
## CS 조사 리포트

### 문의 요약
- 채널: <channel>
- 발생: <timestamp KST>
- 사용자: <이름 또는 익명>
- 현상: <한 줄 요약>
- 재현 단계: <있으면 bullet>

### Datadog 에러 (service=<svc>, <from>~<to>)

#### 이슈 TOP N
1. [ISSUE-XXX] <error.type>: <error.message>  N회 / 마지막 <ts>
   스택: <file>:<line>

#### 관련 로그
- <ts> | <http.url> → <http.status_code> | <error.message>

### 코드 위치

| 레이어 | 파일:라인 | 내용 |
|--------|----------|------|
| Controller | `<path>:<line>` | 엔드포인트 |
| UseCase/Service | `<path>:<line>` | 비즈니스 로직 |
| Repository | `<path>:<line>` | 쿼리 |

### 추정 원인
- (로그 + 코드 기반 1~3줄 — 구체적 조건 명시)

### 영향 범위
- 에러 발생: N회 / 영향 유저: (trace_id 기반 추정)
- 관련 엔드포인트: top 3

### 재현·확인 포인트
- (코드 기반으로 재현 조건 또는 추가 확인이 필요한 항목)

---
Datadog 링크: https://app.datadoghq.com/logs?query=service:<svc>+env:prod&from=<from>&to=<to>
```

raw JSON 전체 덤프 금지. 필요한 필드만 요약.

---

## Phase 5 — 상담사 대응 보고서

Phase 4 종합 보고를 바탕으로, 기술 지식이 없는 상담사가 고객에게 바로 안내할 수 있도록 쉬운 말로 작성한다.

**원칙:**
- 개발 용어(스택 트레이스, 쿼리, 예외 클래스명 등) 사용 금지
- 고객 관점의 언어로 설명
- 상담사가 판단할 필요 없이 바로 행동할 수 있도록 명확하게 작성

```
---

## 📋 상담사 대응 보고서

### 원인 유형
<!-- 아래 중 하나를 선택하고 간단히 설명 -->

| 유형 | 설명 |
|------|------|
| ✅ 고객 실수 | 고객이 잘못된 방법으로 사용한 경우 |
| 🐛 시스템 버그 | 서비스 내부 오류로 고객 의도대로 동작하지 않은 경우 |
| 📊 데이터 이슈 | 고객 데이터가 특정 조건에서 비정상 상태인 경우 |
| ℹ️ 정상 동작 | 의도된 동작이나 고객이 오해한 경우 |
| 🔍 추가 확인 필요 | 로그·코드만으로 원인을 단정할 수 없는 경우 |

**선택:** <유형 이름>

---

### 무슨 일이 있었나요? (현상 설명)
<!-- 고객이 경험한 현상을 상담사가 이해하기 쉽게 1~3줄로 설명 -->

<현상 설명>

---

### 왜 이런 일이 발생했나요? (원인 설명)
<!-- 기술 용어 없이 일반 언어로 원인을 설명. "시스템이 ~를 처리하는 과정에서 ~한 조건이 충족되지 않아..." 형태 -->

<원인 설명>

---

### 상담사 행동 지침

#### 고객 안내 방법
<!-- 고객에게 직접 전달할 수 있는 안내 문구 예시. 복사해서 바로 쓸 수 있도록 작성 -->

> (안내 예시 문구)
> 
> 예: "안녕하세요, 확인 결과 현재 시스템에서 ~한 경우 ~이 발생하는 문제가 확인되었습니다. 현재 개발팀에서 수정 중이며, ~까지 처리 예정입니다. 불편을 드려 죄송합니다."

#### 상담사 조치 항목
<!-- 상담사가 직접 해야 하는 행동을 체크리스트로 -->

- [ ] <조치 항목 1> — <이유 또는 방법>
- [ ] <조치 항목 2> — <이유 또는 방법>

#### 개발팀 에스컬레이션
<!-- 개발팀에 전달해야 하는 경우: 필요 / 불필요 / 이미 인지 중 -->

| 항목 | 내용 |
|------|------|
| 에스컬레이션 여부 | 필요 / 불필요 / 이미 인지 중 |
| 전달 내용 | <개발팀에 전달할 내용 요약> |
| 우선순위 | 긴급(당일) / 일반(금주 내) / 낮음(다음 스프린트) |

#### 임시 우회 방법 (있는 경우)
<!-- 개발 수정 전에 고객이 직접 해결할 수 있는 방법이 있다면 안내 -->

<임시 우회 방법 또는 "현재 임시 우회 방법 없음">

---

### 유사 케이스 재발 시
<!-- 같은 현상으로 다른 고객 문의가 오면 어떻게 대응할지 -->

<재발 시 대응 방법 1~2줄>
```

---

## 제약

- Datadog 서비스명을 모르면 조회하지 않고 `(Datadog 조회 불가 — 서비스 미확인)` 표기
- 코드가 없는 레포(FE 등)는 코드 탐색 생략 후 명시
- 스택 없이 에러 메시지만 있으면 키워드 grep으로 최대한 추적
- 스레드에 실제 문의 내용이 없으면 — 파악 불가 사유를 출력하고 추가 정보 요청
