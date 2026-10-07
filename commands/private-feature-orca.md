---
description: 개인 프로젝트 풀 파이프라인을 Orca orchestration으로 실행한다 — PRD→검수→시니어 설계→pm 정합→구현 wave→리뷰→PR 머지를 orca Run/Task DAG/supervised worker로 수행. 요구사항 텍스트 또는 기존 PRD 경로를 인수로 받는다. 사용자 게이트 2회. in-process 서브에이전트로 도는 버전은 /private-feature.
requires: L2
roles: [prd.author, prd.review, design.be, design.fe, design.db, design.review, plan.coordinate, implement.be, implement.fe, review.code]

---

라우팅 (roles.json active_profile 해석):
!`~/.harness/bin/harness role --compact prd.author prd.review design.be design.fe design.db design.review plan.coordinate implement.be implement.fe review.code`

# /private-feature-orca — 개인 프로젝트 풀 파이프라인 (Orca orchestration)

요구사항: `$ARGUMENTS`

`/private-feature`와 **동일한 파이프라인**을 in-process 서브에이전트 대신 **Orca supervised worker**로 실행한다. 메인 세션은 coordinator 역할만 하며, 코드·문서는 전부 worker가 만든다. 산출물 저장 루트: `/Users/biuea/Desktop/dpdpdndn/프로젝트/{앱 카테고리}/`.

## 이 커맨드를 쓰는 기준

| 상황 | 선택 |
|---|---|
| 파이프라인 전체를 orca에 기록·추적하고 싶다 | `/private-feature-orca` |
| wave 병렬 구현을 실제 worktree 격리로 돌리고 싶다 | `/private-feature-orca` |
| 토큰 비용을 아끼고 싶다 / 단일 도메인 소규모 | `/private-feature` 또는 `/private-implement` |

**전면 변환이므로 Step 1~4의 모든 단계를 orca task로 선언한다.** 메인 세션이 `Agent(...)`로 직접 스폰하지 않는다 — 각 worker가 자기 터미널 안에서 해당 `private-*` 에이전트를 호출한다 (2-hop).

---

## Step 0 — 전제 확인 및 Run 생성

1. **개인 프로젝트 마커** — `[ -f "$(git rev-parse --show-toplevel)/.claude/private-project" ]`. 없으면 중단하고 안내한다 (`touch .claude/private-project` + 커밋).
2. **orca 준비** — `orca status --json` 이 `runtime.state: ready` 여야 한다. 아니면 `orca open` 후 재확인. 실패 시 중단하고 `/private-feature`(in-process)로 폴백을 제안한다.
3. **앱 카테고리** — 인수에서 특정되지 않으면 저장 루트 디렉토리 목록을 보여주고 사용자에게 확인한다. 임의로 새 카테고리를 만들지 않는다.
4. **Run 생성** — 이 터미널을 coordinator로 바인딩한다.

```bash
orca orchestration run-create --objective "<앱 카테고리> / <기능명> 풀 파이프라인" --json
```

인수가 기존 PRD 경로면 Step 1의 T1·T2를 건너뛰고 T3부터 선언한다.

---

## Task DAG 선언 규약

각 단계를 **먼저 task로 선언하고** `--deps`로 순서를 강제한다. coordinator가 순서를 기억하는 게 아니라 DAG가 강제하게 만든다.

```bash
orca orchestration task-create --task-title "<단계명>" --display-name "<에이전트명>" \
  --spec "<아래 worker spec 템플릿>" --deps '["<선행 task_id>", ...]' --json
```

`task-list --ready --brief --json`을 coordinator의 외부 메모리로 쓴다. 의존 사슬은 4단계를 넘기지 않는다.

## 실행 규약 — role → orca worker

단계는 **role** 로만 지정한다. 어느 런타임·모델로 돌지는 `roles.json` 의 active_profile 이 정한다 ([ADR 0002](../docs/decisions/0002-llm-runtime-routing.md)). 이 커맨드는 그 해석을 **orca worker 플래그로 옮기는 것**만 담당한다.

| roles.json | orca worker-start 플래그 |
|---|---|
| `runtime: claude` | `--agent claude` + `[역할] A` 템플릿 |
| `runtime: codex` | `--agent codex` + `[역할] B` 템플릿 |
| `tier` 의 모델 | `--model <위 라우팅 표의 모델>` |
| codex `tier` 의 effort | `--effort <high\|medium\|low>` (`--model` 없이 못 쓴다) |

- 배정을 이 문서에 다시 적지 않는다 — **위 라우팅 표가 유일한 근거**다. 프로파일을 바꾸면 표가 따라 바뀐다.
- 지정 후 receipt 의 `launch.requested` / `launch.effective` 로 반영을 확인한다.
- 실행 전 두 계정을 확인한다: `orca account list --json`.

- **`private-*` 에이전트 정의(`~/.claude/agents/`)는 claude에만 존재한다.** codex worker는 그 정의를 부를 수 없으므로 `~/.claude/rules/` 파일을 직접 읽게 지시한다 (아래 B 템플릿).
- 리뷰 worker가 `gh pr merge`까지 수행하므로 codex 터미널에 `gh` 인증이 되어 있어야 한다.

### worker spec 템플릿

모든 `--spec`은 아래 4블록을 포함한다. `[역할]`만 A/B로 갈리고 나머지 3블록은 동일하다.

**A. claude worker — 코드 구현 전용**

```
[역할] 너는 Orca supervised worker다. 이 작업은 반드시 서브에이전트로 수행하고,
       메인 컨텍스트에서 직접 산출물을 쓰지 않는다.
       담당 role: <implement.be | implement.fe | implement.mysql | implement.mongodb |
                  implement.kafka | implement.redis>
       그 role 의 subagent_type·model 은 `~/.harness/bin/harness role <role>` 의 invoke 를 그대로 쓴다.
```

**B. codex worker — 문서·티켓·리뷰**

에이전트 정의가 없으므로 규칙 파일을 경로로 지정해 읽힌다. **역할별로 아래 목록만** 넣는다 (전부 넣지 않는다 — 컨텍스트 낭비).

```
[역할] 너는 Orca supervised worker다. 작업 전에 아래 규칙 파일을 전부 읽고 그대로 따른다:
       <역할별 규칙 파일 목록>
       ~/.claude/rules/output-style.md        (항상 — 문체·수치 구체성)
       ~/.claude/rules/COMPLETION-RULE.md     (항상 — 완료 단언 조건)
       추측 금지. 모든 지적·진술은 `파일#메서드` 또는 `파일:라인`으로 근거를 표기한다.
```

| 역할 | 읽힐 규칙 파일 |
|---|---|
| PRD 작성·검수 | `private-prd-template.md` |
| 시니어 설계 BE | `private-tdd.md`, `private-be-code-convention.md`, `private-be-architecture-rule.md`, `mermaid.md` |
| 시니어 설계 FE | `private-tdd.md`, `private-fe-convention.md`, `mermaid.md` |
| 시니어 설계 DBA | `private-tdd.md`, `private-db-schema-convention.md`, `private-mongodb-convention.md` |
| 티켓 분해 (시니어·TPM) | `private-ticket.md`, `private-branch-convention.md` |
| PM 정합 검증 | `private-prd-template.md`, `private-tdd.md` |
| 코드 리뷰 | `private-code-review-criteria.md`, `private-be-code-convention.md`, `private-be-architecture-rule.md`, `private-fe-convention.md` |
| 인프라 리뷰 | `private-db-schema-convention.md`, `private-kafka-convention.md`, `private-redis-convention.md`, `private-mongodb-convention.md` |

> 리뷰 worker spec에는 **"변경 파일을 전수 Read한다 — diff만 보고 판단 금지"** 와 p0~p2 존재 시 `REQUEST_CHANGES` verdict 규칙을 명시적으로 반복해 넣는다. 에이전트 정의가 없어 이 행동 규율이 프롬프트로만 강제되기 때문이다.

**공통 3블록**

```
[입력] <PRD 경로 / 설계 문서 경로 / 티켓 경로 / 선행 worker 산출물 경로>
[산출] <생성할 파일 절대경로 또는 변경 대상 모듈>
[보고] 작업 후 worker_done을 정확히 1회 보낸다. body **첫 줄**은 반드시 아래 형식이다:
       VERDICT: PASS | NEEDS_REVISION | REQUEST_CHANGES | APPROVED | BLOCKED
       둘째 줄부터 산출물 절대경로 목록, 그 아래 3문장 요약(한 일 / 발견 / 남은 것).
       검증 아티팩트(테스트 raw 출력·빌드 로그)를 body에 포함한다 — COMPLETION-RULE §2.
```

worker가 보내는 형식:

```bash
orca orchestration send --type worker_done --subject "<단계명> <verdict>" \
  --body "VERDICT: PASS
<산출물 경로들>
<3문장 요약 + 검증 아티팩트>" \
  --task-id <task_id> --dispatch-id <dispatch_id> --outcome succeeded \
  --files-modified "path/a,path/b" --json
```

### worker 배치 규칙

| 단계 | 배치 | 근거 |
|---|---|---|
| PRD·설계·티켓 분해 (문서만 생산) | `--worktree current --agent codex` | 산출 루트가 절대경로라 격리 불필요. fresh agent 터미널만 뜬다 |
| 구현 티켓 | `--worktree new-top-level --name <티켓ID> --setup run --agent claude` | 전역 CLAUDE.md §5 worktree 격리 + Single Writer per File |
| 티켓 리뷰 | `--worktree name:<티켓ID> --agent codex` | 리뷰 대상 체크아웃 필요 + 구현(claude)과 교차 |

- 구현 worker에 **`--base-branch`를 넘기지 않는다** — 레포 기본 base(`origin/main`)를 쓰게 한다. private-branch-convention의 "origin/main 기준 숏텀 티켓 브랜치"와 일치한다.
- 티켓 브랜치를 다른 티켓 브랜치 위에 쌓지 않는다 (`--no-parent` 성격의 top-level 고정).
- 모델 지정이 필요하면 `--model <provider id> --effort high`를 함께 넘긴다 (`--effort`는 `--model` 없이 쓸 수 없다).

### 표준 기동 경로 — 워밍된 터미널 재사용 (실전 검증)

**콜드 스타트 주입은 claude·codex 양쪽에서 100% 유실된다.** 아래 순서를 표준으로 쓴다.

1. **첫 worker만** `worker-start --worktree <대상> --agent <claude|codex>`로 띄운다.
2. 유실을 전제하고 아래 "전달 검증"을 수행해 복구한다.
3. **그 뒤로는 같은 터미널을 재사용한다** — `worker-start --task <다음> --terminal <handle>`. 워밍된 TUI에는 주입이 한 번에 들어가고 capability도 정상이다.
4. 다른 worktree의 터미널을 재사용할 때는 `--worktree name:<티켓ID> --terminal <handle>`을 함께 넘긴다. 생략하면 `terminal_worktree_mismatch`로 거부된다.
5. **리뷰어만은 예외로 새 터미널을 쓴다** — 같은 터미널이 작성과 검수를 겸하면 자기 검토가 된다. 실측에서 독립 터미널 재검수가 자기 검토가 놓친 결함 2건을 추가로 잡았다.

### 사용량 한도 — 시작 전 확인 (파이프라인을 통째로 멈춘다)

구현이 전부 claude 배정이라 **claude 한도에 걸리면 구현 단계 전체가 정지**한다. wave를 열기 전에 확인한다.

- 한도에 걸린 claude 터미널은 `What do you want to do? 1. Stop and wait for limit to reset` 프롬프트에서 멈춘다. **`grep "session limit"`으로는 이 상태를 못 잡는다** — 터미널 tail을 직접 읽어 이 선택지가 떠 있는지 봐야 한다.
- 걸렸으면 `terminal send --text "1" --enter`로 파킹하고, dispatch는 `worker-abandon`, task는 `task-update --status blocked --result '{"reason":"..."}'`로 남긴다. 미커밋 작업은 worktree에 그대로 보존되므로 재개 시 이어서 쓴다.
- 대규모 wave를 열기 전에 남은 한도를 가늠하라. 티켓 하나가 claude 세션 40분 이상을 쓴다(실측: BE-85 46분).

### worker-start 직후 프롬프트 전달 검증 (필수 — 실측 확인된 결함)

**`worker-start`의 `stage: "input_accepted"`는 프롬프트가 실제로 제출됐다는 뜻이 아니다.** 에이전트 TUI가 부팅 중(codex `model: loading`, claude 초기화)일 때 주입이 일어나면 입력이 유실되거나 입력창에 남은 채 제출되지 않는다. 이 상태로 `check --wait`하면 **몇 분을 기다려도 `count: 0`만 돌아온다** (claude·codex 양쪽 최초 기동에서 재현됨).

start 직후 반드시 확인한다:

```bash
orca orchestration worker-read --dispatch <dispatch_id> --limit 25 --json
```

| 관찰 | 판정 | 조치 |
|---|---|---|
| 작업이 진행 중인 출력 | 정상 | 그대로 `check --wait` |
| spec 텍스트가 입력창에 남아 있음 (claude `⏵⏵ bypass permissions on`, codex 배너 + 플레이스홀더) | **미제출** | `orca terminal send --terminal <agent_terminal_handle> --text "" --enter --json` 로 제출 |
| 배너만 있고 spec 텍스트가 아예 없음 | **유실** | `worker-stop --dispatch <id>` → `worker-start --task <task> --retry-of <id> --worktree <동일> --agent <동일>` (2회차는 바이너리가 워밍돼 대개 성공) |

- **`terminal send`로 수동 제출한 worker는 `worker-release`가 `user_takeover`로 거부한다** (`state: retained`). 완료 후 `orca terminal close --terminal <handle> --json`로 직접 닫아 잔여 터미널을 남기지 않는다.
- 저수준 `terminal create --command codex` → `terminal wait --for tui-idle` → `dispatch --inject` 경로는 이 환경에서 `Timed out waiting for terminal handle after creation`으로 실패했다. **`worker-start` + 위 검증**을 표준 경로로 쓴다.
- wave에서 worker N개를 start했으면 **N개 전부에 대해** 이 검증을 수행한 뒤 `check --wait`에 들어간다.

### 대기·정리 규칙

```bash
orca orchestration check --wait --types worker_done,escalation,question --timeout-ms 900000 --json
```

- **한 wave의 독립 worker를 전부 start한 뒤 한 번만 wait한다.** worker 하나 띄우고 기다리는 직렬화는 분해 실패다.
- Delivery의 **모든 메시지를 처리한 뒤** `--ack <delivery_id>` 한다. `question`은 `reply --id <msg_id> --body <답변>`으로 답한다.
- timeout이나 `{count:0}`은 실패가 아니다 — 롤링 wait을 계속한다. 하트비트·TUI 활동만으로 worker를 죽이지 않는다.
- 각 `worker_done` 처리 후: 같은 에이전트에 즉시 후속 task가 있으면 `worker-show --dispatch <id> --json`의 `worker.agent_terminal_handle`로 `worker-start --task <다음> --terminal <handle>`, 아니면 `worker-release --dispatch <id> --json`.

### 재작업 루프 (orchestration에 프리미티브가 없는 부분)

`VERDICT`가 `NEEDS_REVISION` / `REQUEST_CHANGES`면 coordinator가 직접 루프를 돈다.

1. 지적 목록을 원 작성 task의 worker에게 전달한다 — `orca orchestration send --to dispatch:<원 dispatch> --subject "보완 요청" --body "<지적 목록>"` (터미널이 살아 있을 때) 또는 `worker-start --task <원 task> --retry-of <dispatch> --worktree <동일> --agent <원 task와 동일한 에이전트>`. 재작업은 배정을 바꾸지 않는다 — 바꾸면 지적 맥락이 끊긴다.
2. 재검수 task를 다시 start한다.
3. **최대 2회**. 3회째는 사용자에게 에스컬레이션한다 — 한 task에 3회 연속 실패가 쌓이면 dispatch가 circuit-break되어 task가 `failed`로 확정된다.

---

## Step 1 — PRD

```
T1 private-prd-writer   (deps: 없음)
T2 private-prd-reviewer (deps: [T1])
```

- T1 worker가 질문 목록을 반환하면 (`ask` 또는 `VERDICT: BLOCKED`) **사용자에게 그대로 전달**하고 답을 `reply`로 돌려준다. 가정하지 않는다.
- T2가 `NEEDS_REVISION`이면 위 재작업 루프.
- **게이트 ① (사용자 승인)** — 다음 task를 실제로 막는다.

```bash
orca orchestration gate-create --task <T3> --question "PRD 승인하고 설계로 진행할까요?" --options '["승인","보완 요청"]' --json
# 사용자 답을 받은 뒤:
orca orchestration gate-resolve --id <gate_id> --resolution "승인" --json
```

보고 내용: PRD 경로 · Goals/Non-Goals · P0 요구사항 · 검수 verdict.

---

## Step 2 — 설계 (be 먼저 → fe/dba 병렬)

```
T3 private-senior-be  (deps: [T2])   — TDD + BE 티켓 + API 계약
T4 private-senior-fe  (deps: [T3])   — FE 설계 + FE 티켓 (API 계약 소비)
T5 private-senior-dba (deps: [T3])   — DB 설계 (테이블 변경 없으면 선언 자체를 생략)
T6 private-senior-pm  (deps: [T4,T5]) — PRD 정합 검증
```

- T3 완료 후 **T4·T5 worker를 한 번에 start하고** 그 다음 한 번만 `check --wait`한다.
- T6가 `NEEDS_REVISION`이면 지적을 해당 시니어 task로 되돌려 재작업 (최대 2회).
- **게이트 ② (사용자 승인)** — `gate-create --task <T7>`. 이 승인은 구현→리뷰→PR→자동머지까지의 자동 진행을 포함한다.

보고 내용: 설계 문서 경로 · 채택 방안 · 티켓 DAG(wave 너비 분포) · 무중단 배포 시나리오.

> wave 너비가 전부 1~2인 직선형 DAG면 분해 실패다 — 게이트를 통과시키지 말고 재분해를 요구한다 (private-ticket).

---

## Step 3 — 구현 (승인 후 자동)

```
T7 private-tpm (deps: [T6]) — 도메인 간 통합 DAG 산출
```

T7 worker는 **코드를 짜지 않고** 통합 DAG(인프라 wave → BE/FE wave, 티켓별 의존·수정 예상 파일 집합)를 산출물 md로 낸다. coordinator가 그 DAG를 읽어 **orca task로 등록**한다.

### 인프라 wave

```
Ti-*  private-<mysql|mongodb|kafka|redis>-implementer (deps: [T7])
Ti-R  private-infra-reviewer                          (deps: [Ti-*])
```

- 인프라 worker들은 서로 독립이면 동시 start.
- `Ti-R`이 `REQUEST_CHANGES`면 해당 implementer로 되돌린다. **PASS 전에 BE wave를 열지 않는다.**

### BE/FE wave

wave마다:

```
Tw-<티켓ID>   private-<be|fe>-implementer (deps: [직전 wave 티켓들 / Ti-R])
Tw-<티켓ID>-R private-code-reviewer       (deps: [Tw-<티켓ID>])
```

- **같은 wave의 티켓 worker를 전부 start한 뒤 한 번만 wait한다.** 티켓당 `--worktree new-top-level --name <티켓ID>`.
- 티켓 spec에는 티켓 md 경로 + TDD 경로 + "테스트 먼저(RED→GREEN→REFACTOR)"를 명시한다. worker 안에서 role `implement.be`가 TDD 순서를 강제한다.
- 공용 테스트 헬퍼·fixture는 wave 1 계약 티켓이 소유한다 — 후행 티켓 spec에 "소비만 하고 만들지 않는다"를 적는다 (private-ticket).
- 리뷰 `REQUEST_CHANGES`면 해당 implementer worker를 재기동해 수정 → 재리뷰. **wave의 모든 리뷰가 통과해야 다음 wave를 연다.**

진행 보고는 `orca orchestration task-list --brief --json`을 도메인 × wave × 티켓 표로 사용자에게 중계한다. 게이트를 막는 실패는 즉시 보고한다.

---

## Step 4 — PR·머지 (자동)

브랜치 전략은 private-branch-convention을 따른다 — **각 티켓 브랜치를 각자 `main`으로 머지**한다. 전체 기능을 장수명 피처 브랜치에 모아 통째로 머지하지 않는다.

티켓 worker의 spec 말미에 아래를 포함시켜 worker 자신이 수행하게 한다:

1. 변경 모듈 테스트를 **실제 실행해 exit 0 확인** 후 push — `git push ... # tests-passed`. 파이프로 exit code를 가리지 않는다 (`set -o pipefail`).
2. `gh pr create --base main` — 제목 `[티켓ID] - <type> : 제목`, 본문에 PRD·TDD 링크 + 변경 요약.
3. PR URL을 `worker_done` body에 포함한다.

리뷰 task(`Tw-*-R`)의 worker가 PR 재리뷰 후 p0~p3 전부 반영을 확인하면 `gh pr merge --squash --auto # p3-reflected`를 실행하고 티켓 브랜치를 삭제한다. `--no-verify`는 절대 쓰지 않는다.

**`main` 머지 = dev 배포** — 여기까지가 이 파이프라인의 범위다.

## prod 배포 (별도 요청 시)

자동 진행하지 않는다. 사용자가 요청하면 role `qa` task를 새로 만들어 실행한다 (dev 실구동 E2E + 회귀). **verdict PASS 없이 prod 배포 금지.** FAIL이면 버그 리포트를 담당 implementer task로 되돌리고 QA 전체를 재실행한다. 배포는 `/private-release`.

---

## 금지 사항

- 메인 세션이 `Agent(...)`로 파이프라인 단계를 직접 스폰하는 것 — 전면 변환이므로 모든 단계는 orca task/dispatch 기록을 가져야 한다. 사고로 밖에서 돌렸다면 그 사실을 그대로 말하고, 필요한 작업만 새 dispatch로 재실행한다.
- `orca orchestration reset` — 활성 조율 중 실행 금지.
- worker를 timeout·TUI idle·heartbeat만 보고 `worker-stop`·`terminal close` 하는 것.
- 게이트 ①② 없이 다음 단계 task를 start하는 것.

## 완료 보고

> 완료 단언은 `rules/COMPLETION-RULE.md` §1~4를 모두 충족해야 한다. 아래 표를 쓰기 전에 `task-list --json`을 실제로 실행한다.

```
## /private-feature-orca 결과: {in-progress | 완료}
- Run: {run_id}
- PRD / TDD / 설계 / 티켓: {경로들}
- Task DAG: {task-list --json 요약 — 단계 × status}
- 구현: {wave × 티켓 완료 표}
- 리뷰: {verdict 이력}
- PR: {URL, 머지 여부 + raw 출력}
- 미해결 / 미정리 worker: {있으면 dispatch_id}
```

