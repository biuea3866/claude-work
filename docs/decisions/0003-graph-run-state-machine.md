# ADR 0003 — 그래프 실행을 LLM 밖의 상태 기계로 분리

- **날짜**: 2026-08-13
- **상태**: 채택 · 반영 완료 (`bin/harness run`, `bin/harness validate`) · **부분 개정 → [ADR 0005](./0005-dispatcher-execution-layer.md)**
- **개정 범위**: "CLI 가 LLM 을 부르지 않는다" 한 문장. 디스패처는 Agent 툴이 아니라 헤드리스 CLI 를 subprocess 로 부르므로 "어느 런타임에서든 동일" 원칙은 유지된다. 판단(ready 셋·계약·게이트)과 호출의 분리 구조는 그대로다 — 호출 주체가 하나 늘었다.
- **관련**: [orchestration/README.md](../../orchestration/README.md), [contracts/README.md](../../contracts/README.md), [ADR 0002](./0002-llm-runtime-routing.md), [capabilities.md](../../capabilities.md)

## 배경

`orchestration/private-feature.json`은 노드·의존·계약·게이트·재시도를 전부 선언했지만 **그것을 실행하는 주체가 없었다.** 결과:

- 어느 노드가 열렸는지를 **메인 세션의 기억**이 관리했다. 컨텍스트가 요약되면 그 상태가 사라진다.
- `output_contract` 선언이 9개 노드에 있었지만 **검증하는 코드가 없었다** — 계약은 주석과 같았다.
- `runs/` 디렉토리가 규범 문서에 6번 등장하는데 **한 번도 생성되지 않았다.**
- 재시도·게이트·강등 정책이 JSON에만 있고 실행 시 아무 효력이 없었다.

## 결정

**상태 기계와 LLM 호출을 분리한다.** `bin/harness run`은 LLM을 부르지 않는다.

| 역할 | 주체 |
|---|---|
| 무엇을 실행할 차례인가 (ready 셋) | `harness run` |
| 어느 런타임·모델로 부르는가 | `harness run` (roles.json 해석 → `invoke` 문자열) |
| **실제 호출** | **메인 세션** (Agent 툴 / `codex exec`) |
| 산출물이 계약을 만족하는가 | `harness run done` → `validate_result` |
| 상태·이력 기록 | `runs/<run-id>/{state.json, journal.jsonl, <node>/result.json}` |

CLI가 LLM을 부르지 않는 이유는 단순하다 — **Agent 툴은 메인 세션만 쓸 수 있다.** CLI가 서브에이전트를 스폰하려면 런타임을 흉내내야 하고, 그 순간 "어느 런타임에서든 동일" 원칙이 깨진다. 그래서 CLI는 **판단과 기록**을, 세션은 **호출**을 맡는다.

## 계약 검증 — 스키마 + 의미 규칙

`jsonschema` 의존성을 두지 않고 draft 2020-12의 **사용 중인 부분집합**만 구현했다 (`type`·`required`·`properties`·`additionalProperties:false`·`enum`·`pattern`·`minLength`·`minItems`·`minimum`·`maximum`·`uniqueItems`·`items`).

그보다 중요한 건 **스키마로 표현할 수 없는 하네스 규칙**이다. 이것들을 `semantic_checks`로 강제한다.

| 계약 | 의미 규칙 | 근거 |
|---|---|---|
| `implementation-result` | `status=done` 인데 `exit_code≠0` / 미실행 / 아티팩트 없음 → 위반 | [COMPLETION-RULE](../../rules/COMPLETION-RULE.md) §1~2 |
| `implementation-result` | `red_first=false`, 또는 `red_first`인데 증거 없음 → 위반 | [core-directives](../../rules/00-core-directives.md) §1 |
| `review-verdict` | findings 등급과 verdict 불일치 (p0~p2 있는데 APPROVED 등) | [private-code-review-criteria](../../rules/private-code-review-criteria.md) |
| `review-verdict` | `files_read < files_changed` 인데 skipped 사유 없음 | 전수 Read 원칙 |
| `design-doc` | 모든 wave 너비가 1~2 → 분해 실패 | [private-ticket](../../rules/private-ticket.md) fan-out 게이트 |
| `design-doc` | 같은 wave 안 `files_touched` 교집합 | Single Writer per File |
| `design-doc` | `depends_on` 이 같거나 뒤 wave를 가리킴 | wave 위상 정합 |

**"완료" 단언이 기계 검증을 통과해야 완료가 된다.** 사람이나 모델의 선언으로는 `completed`가 되지 않는다.

## fanout — 티켓 DAG를 노드 의존으로 옮긴다

`implement` 노드는 `plan` 산출물의 `tickets[]`로 복제된다. 자식 노드의 의존은 `[plan] + [implement[<depends_on>]]`이다 — **티켓의 `depends_on`을 그대로 노드 엣지로 옮긴다.** 이걸 빼면 wave 순서가 사라져 선행 티켓 없이 후행이 열린다(구현 중 실제로 발생시켜 잡았다).

role은 `fanout.role_from`이 가리키는 티켓 필드에서 읽는다 (ADR 0002 참조) — 접두사 추론이 아니다.

## 재작업 루프백

리뷰가 `REQUEST_CHANGES`면 결과는 기록하되 게이트를 열지 않고, `retry.to`의 노드(및 그 fanout 자식)를 `pending`으로 되돌린다. 기본값이 넓으면 `--rework "implement[BE-01]"`로 좁힌다.

**자식만 좁혀 재작업할 때 부모도 미완료로 되돌린다** — 그러지 않으면 부모가 `completed`로 남아 후행 리뷰가 재작업 완료 전에 다시 열린다(구현 중 발생시켜 잡았다).

## 대안과 미채택 사유

| 대안 | 미채택 사유 |
|---|---|
| CLI가 서브에이전트까지 스폰 | Agent 툴은 메인 세션 전용. 런타임을 흉내내는 순간 런타임 중립성이 깨진다 |
| 상태를 메인 세션 컨텍스트에 유지 | 컨텍스트 요약 시 소실. 재개·감사 불가 — 애초의 문제 |
| `jsonschema` 의존성 추가 | 하네스는 파이썬 표준 라이브러리만으로 돌아야 한다. 필요한 문법은 부분집합으로 충분하고, 정작 중요한 규칙은 스키마로 표현이 안 된다 |
| 계약 위반을 경고로 처리 | 통과시키면 계약이 아니다. `retry.on: [contract_violation]`이 이미 재시도 경로를 정의해 뒀다 |
| 스킬 본문에 단계 순서를 계속 서술 | 순서를 두 곳(그래프·스킬)에 두면 드리프트. 스킬은 "무엇을"만, 순서는 그래프가 소유 |

## 파급

- `/private-feature` 스킬에 **실행 상태 관리** 절이 생겼다 — 단계 진행이 `run next` → 호출 → `run done`으로 고정된다.
- `runs/`가 실제로 생성된다 (`.gitignore` 대상).
- `contracts/README.md`가 예고했던 "외부 의존성 없는 검증기"가 실체가 됐다.
- 노드 스펙에 `retry.to`가 추가됐다 — 루프백 대상을 그래프가 선언한다. lint가 실재 여부를 검사한다.

## 미결

- **`timeout_sec`은 아직 강제되지 않는다.** 선언만 있고 CLI가 시간을 재지 않는다 — 호출 주체가 메인 세션이라 타임아웃 관측도 그쪽이어야 한다.
- **`on_failure: degrade`** 는 `halt`/`skip`과 달리 아직 별도 처리가 없다 (현재 `failed`로 떨어진다).
- 엔드투엔드 검증은 **픽스처로 했다.** 실제 codex/claude 호출로 한 바퀴 돌린 기록은 아직 없다.
