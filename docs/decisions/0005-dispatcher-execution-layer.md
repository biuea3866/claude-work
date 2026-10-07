# ADR 0005 — 실행 계층(디스패처) 신설, ADR 0003 부분 개정

- **날짜**: 2026-08-27
- **상태**: 채택 · 반영 완료 (`orchestration/runner/`, `harness run dispatch|wave`, `harness test`)
- **관련**: [ADR 0003](./0003-graph-run-state-machine.md) (부분 개정) · [ADR 0004](./0004-runtime-budget-failover.md) · [ADR 0002](./0002-llm-runtime-routing.md) · [설계 문서](../architecture/20260827-multiagent-runner-tdd.md)

## 배경

하네스는 멀티에이전트 파이프라인의 **선언**을 전부 갖췄다 — role 간접화, 그래프 9노드, 산출물 계약 3개, 상태 기계, 강등 사다리, 예산 게이트. 없는 것은 **실행**이었다.

`harness run next` 는 `invoke_command` 가 만든 문자열을 출력하고 리턴했다. 프로세스를 띄우는 코드가 없었다. 결과:

- **"동시 실행 가능"이 사실 진술이 아니라 부탁이었다.** 실제 동시성은 메인 세션이 한 메시지에서 여러 도구를 부르느냐에 달렸다.
- 그래서 **사후 감사 도구가 따로 존재했다** — `hooks/private-wave-spawn-log.sh` 가 스폰 시각을 적재하고 `hooks/lib/wave-audit.py` 가 20초 간격으로 병렬/직렬을 판정한다. 감사 도구의 존재가 기계 강제의 부재를 증명한다.
- `expand_fanout` 은 티켓 자식을 만들었지만 **각 자식이 어느 디렉토리에서 도는지 정하지 않았다.** `print_next` 는 `cwd='<worktree>'` 라는 자리표시자를 그대로 출력했다.
- 런타임 호출이 `invoke_command` 3분기로 코드에 박혀 있었다 — 새 런타임은 코드 변경이었다.
- 예산 게이트는 **사전 예측**만 했다. 노드가 실제로 429 로 죽었을 때 대체 런타임으로 넘기는 경로가 없었다.
- `roles.json#bindings.cross-review` 의 "작성자와 리뷰어를 다른 런타임에" 는 **주석**이었다. 프로파일을 편집해 같은 런타임으로 만들어도 lint 가 통과했다.

같은 문제를 `gitkraken-clone-app/.agent/orchestration` 이 이미 풀어 두었다 (러너 837줄 + 티켓 wave 실행기 460줄).

## 결정

**상태 기계는 그대로 두고, 그 옆에 실행 계층을 얹는다.**

| 역할 | 주체 | 변화 |
|---|---|---|
| 무엇을 실행할 차례인가 (ready 셋) | `harness run` | 유지 |
| 어느 런타임·모델로 부르는가 | `roles.json` → `resolve_routing` | 유지 |
| **실제 호출** | 메인 세션(Agent 툴) **또는 디스패처(헤드리스 CLI)** | **개정** |
| argv 조립 | `adapters/*.toml` | **신설** — 코드에서 선언으로 |
| 산출물이 계약을 만족하는가 | `harness run done` → `validate_result` | 유지. 자동 경로도 **같은 함수**를 통과한다 |
| 상태·이력 기록 | `runs/<run-id>/{state.json, journal.jsonl}` | 유지 |
| 티켓 워크트리 배치 | `harness run wave` | **신설** |

### ADR 0003 의 어느 문장이 개정되는가

ADR 0003 은 이렇게 적었다 — "CLI 가 서브에이전트를 스폰하려면 런타임을 흉내내야 하고, 그 순간 '어느 런타임에서든 동일' 원칙이 깨진다." 그 근거는 **Agent 툴이 메인 세션 전용**이라는 사실이었다.

디스패처는 Agent 툴을 쓰지 않는다. **헤드리스 CLI(`claude -p`, `codex exec`)를 subprocess 로 부른다** — 메인 세션이 아니어도 되는 경로다. 원칙은 깨지지 않는다.

개정되는 것은 **"CLI 는 LLM 을 부르지 않는다"** 한 문장뿐이다. 판단(ready 셋·계약·게이트)과 호출이 분리돼 있다는 구조는 그대로다 — 호출 주체가 하나 늘었다.

## 왜 러너를 통째로 복사하지 않았나

프로젝트 러너를 그대로 옮기면 **상태 저장소가 둘**이 된다 — `runs/<id>/state.json`(하네스)과 `runs/<ts>-<wf>/run.json`(러너). 어느 쪽이 정본인지 모호해지고, 하네스가 프로젝트보다 **앞서 있는** 것들이 우회된다:

| 하네스에만 있는 것 | 프로젝트에 없음 |
|---|---|
| 계약 의미 규칙 (`semantic_checks`) — TDD RED 증거·wave 너비·Single Writer·verdict 정합 | 스키마 강제만 (codex `--output-schema`) |
| 재작업 루프백 (`--rework`, 부모 되돌리기) | verdict 분기 없음 |
| 강등 사다리 기록 (`degraded`) | 없음 |
| role 간접화 (`roles.json`) | 노드가 vendor 를 직접 든다 |
| journal 이벤트 append | `run.json` 매니페스트만 |

그래서 **실행에 관한 것만** 가져왔다: 어댑터 TOML 스키마, 소진 페일오버, 워크트리 확보, 실행 전 전수 검증, dry-run.

## profiles.toml 을 만들지 않은 이유

프로젝트는 `profiles.toml`(profile → vendor·model·effort)을 별도로 둔다. 하네스는 **만들지 않았다** — `roles.json#bindings` 가 이미 그 역할의 결정적 조회 테이블이다. 프로젝트가 그 파일을 만든 건 role 층이 없어서였다. 둘 다 두면 라우팅 정본이 둘이 된다.

대신 프로젝트가 `profiles.toml` 에 담았던 **실행 예산·권한**을 `roles.json#roles[].exec` 로 흡수했다.

```json
"design.be": {
  "agent": "private-senior-be", "requires": "L2",
  "exec": { "access": "workspace-write", "tools": ["Read", "Grep", ...] }
}
```

`access` 는 **런타임 중립 3등급**이고, 런타임 네이티브 키(claude `permission_mode` / codex `sandbox`)로의 번역은 어댑터 `[access]` 표가 한다. 코드에 런타임 분기를 두지 않기 위해서다.

## 교차 검증을 주석에서 기계 검사로

`roles.json#roles[].verifies` 가 "이 role 이 대상 role 의 산출물을 검증한다"를 선언하고, `harness lint` 가 **모든 프로파일에 대해** 둘의 runtime 이 다른지 검사한다. 같으면 오류다.

```
prd.review   verifies prd.author        (claude ← codex)  ✅
design.review verifies design.be/fe/db  (claude ← codex)  ✅
review.code  verifies implement.be/fe   (codex  ← claude) ✅
review.infra verifies implement.*       (codex  ← claude) ✅
```

`claude-only`·`portable` 프로파일은 런타임이 하나뿐이라 구조적으로 만족할 수 없다. **면제를 선언 없이 허용하면 검사 자체가 무의미해지므로** `_cross_review_exempt` + `_exempt_reason` 을 명시하게 했다. `portable` 이 이 검사를 도입하면서 처음 드러났다 — 그 전까지 아무도 몰랐다.

### 페일오버는 이 불변식을 우회할 수 있다 — 실행 시점에도 막는다

정적 lint 만으로는 부족하다. 노드가 소진으로 다른 런타임으로 넘어가면 검증자와 피검증자가 **실행 시점에** 같은 런타임이 될 수 있고, 설정은 여전히 교차로 보인다.

| 층 | 무엇을 보는가 | 위반 시 |
|---|---|---|
| `harness lint` | `roles.json` 정적 바인딩 | 오류 (exit 1) |
| `build_node_spec` | 피검증자의 **`runtime_used`** | 검증자를 다른 런타임으로 **재배정**(tier 유지) |
| 재배정 불가 | 피검증자가 모든 런타임을 이미 사용 | **디스패치하지 않고 사용자에게 올린다** |
| `dispatch.run_node` | failover 대상 | 금지 런타임으로는 전환하지 않는다 |

재배정·차단은 전부 journal 에 남는다 (`cross-review-reroute` · `cross-review-blocked`). 조용히 같은 런타임으로 돌리지 않는다 — 리뷰가 작성자와 맹점을 공유하는 것은 리뷰가 없는 것보다 나쁘다 (통과했다는 신호를 주기 때문이다).

tier 를 유지하는 이유: 판단 노드의 추론 예산을 낮추면 리뷰 품질이 떨어진다. 런타임만 바꾼다.

`qa` 에는 `verifies` 를 두지 않는다. 산출물을 읽어 판정하는 게 아니라 배포된 기능을 실제로 구동해 PRD 시나리오로 검증하므로, 맹점 공유 논리가 그대로 적용되지 않는다.

## 두 층의 페일오버 — 합치지 않는다

| 층 | 시점 | 판정 근거 | 동작 |
|---|---|---|---|
| 예산 게이트 (ADR 0004) | ready 계산 시 | 누적 사용량 ≥ 임계(주간 80%) | 디스패치 중단 · 사용자 승인 요청 |
| 노드 페일오버 (ADR 0005) | 노드가 죽은 뒤 | 어댑터 `exhaustion_patterns` 매치 | 대체 런타임 **1 hop** 재시도 |

사전 예측은 "마르기 전에 갈아탄다"를, 사후 감지는 "이미 말랐다"를 다룬다. 전자만 두면 임계 아래에서 터지는 일시적 rate limit 에 노드가 전멸하고, 후자만 두면 run 중간에 쿼터가 말라 리셋까지 최대 7일 묶인다.

## 실행 전 전수 검증 — 조용한 오염 차단

프로젝트 운영에서 실측으로 잡힌 사고를 그대로 승계했다.

| 검사 | 없으면 |
|---|---|
| 미치환 `{{자리표시자}}` | 노드가 그 문자열을 요구사항으로 읽는다 |
| 선행 산출물 파일 부재 | **실패가 아니라 침묵이다.** 노드는 "파일이 없다"고만 적고 남은 입력으로 계속 쓴다. 산출물은 멀쩡해 보이는데 근거가 빠진 채 만들어진다 (프로젝트에서 스펙 11건이 이 상태로 돌았다) |
| 같은 wave 소유 경로 교집합 | 병렬 실행이 곧 머지 충돌 |
| 기준 ref 부재 | 티켓이 엉뚱한 커밋 위에 얹힌다 |

하나라도 걸리면 **0개 노드 실행**이다. 노드 실행 중 실패하면 이미 쓴 비용이 날아간다.

## 대안과 미채택 사유

| 대안 | 미채택 사유 |
|---|---|
| 프로젝트 러너 전량 복사 | 상태 저장소가 둘이 된다. 계약 의미 검증·재작업 루프백·강등 기록이 우회된다 |
| 그래프 포맷을 TOML 로 통일 | 두 레포는 그래프를 공유하지 않는다. `contracts`·`lint`·`graph --sync` 가 전부 JSON 경로에 묶여 변경 표면만 커진다. 지금 규모에 과하다 |
| 상주 스케줄러 데몬 (Airflow 형) | 개인 하네스에 상주 프로세스는 과하다. 세션이 부르는 1회성 CLI 로 충분하다 |
| 결정적 리플레이 (Temporal 형) | LLM 노드는 비결정적이라 리플레이가 성립하지 않는다. 산출물 파일을 정본으로 두고 캐시된 결과를 읽는다 |
| `profiles.toml` 신설 | `roles.json#bindings` 와 라우팅 정본이 둘이 된다 |

## 결과

| 지표 | 이전 | 이후 |
|---|---|---|
| 실행 주체 | 없음 (문자열 출력) | `harness run dispatch` |
| 병렬 강제 | 메인 세션 규율 (사후 감사) | ThreadPool — 테스트가 1초×4를 3초 미만으로 실증 |
| 런타임 추가 | `invoke_command` 코드 수정 | `adapters/<id>.toml` 1개 |
| 티켓 워크트리 | 자리표시자 | `harness run wave` 가 자동 확보 |
| 소진 대응 | 사전 예측만 | 사전 예측 + 사후 1 hop 전환 |
| 교차 검증 | 주석 | `harness lint` 오류 + **실행 시점 재배정·차단** |
| 테스트 | 1파일 29건 | 8파일 317건 (`harness test`) |
| 티켓 입력 | 파이프라인 생성 JSON 만 | 손으로 쓴 티켓 md 도 (`harness plan from-tickets`) |

## 실측으로 드러난 것 (2026-08-27 첫 실행)

설계에 없던 결함 4건이 실제 실행에서 드러났다. 전부 반영했다.

| # | 결함 | 증상 | 조치 |
|---|---|---|---|
| 1 | fanout 자식 프롬프트에 티켓 식별 정보 없음 | 자식 18개가 **전부 같은 프롬프트** — 자기 티켓을 알 수 없다 | `# 배정` 섹션 (ID·제목·티켓 md 경로·선행·소유 경로). 계약에 `path` 선택 필드 |
| 2 | `ANTHROPIC_API_KEY` 가 claude 노드 전량 차단 | CLI 가 claude.ai 로그인 대신 그 키를 쓰고 크레딧 부족으로 전부 실패 | 어댑터 `[env] unset` — 자식 프로세스에만 적용 |
| 3 | CLI 가 API 오류에도 exit 0 | 종료 코드만 보면 실패를 성공으로 오판 | `envelope_error_key = "is_error"` |
| 4 | JSON 추출이 잡음에 깨짐 | 실제 CLI 가 봉투 뒤에 비JSON 줄을 섞어 내보내고, 탐욕 정규식이 두 번째 객체까지 삼킴 | `raw_decode` 전수 스캔 후 최대 객체 선택 |

첫 실행에서 확인된 정상 동작: 워크트리 격리(프로세스별 cwd 실측), 실제 병렬(opus·haiku 동시), 어댑터 argv 일치, TDD 순서 준수(테스트 디렉토리 선행 생성).

## 후속

- `run wave` 는 자식 노드에 `cwd` 를 심고 `dispatch_ready` 를 재사용한다. 티켓 브랜치 push·PR·머지는 여전히 스킬(`/private-review`)과 훅이 담당한다 — 디스패처는 하지 않는다.
- `hooks/lib/wave-audit.py` 는 폐기하지 않는다. 기계 강제가 붙은 뒤에도 **회귀 확인**에는 쓸모가 있다 — 다만 1차 방어선에서 격하됐다.
