# orchestration — 그래프 엔지니어링

skills를 엮어 하나의 워크플로우를 구성한다. 그래프가 **다이어그램이 아니라 실행 가능한 정의**가 되려면 노드가 아래를 전부 선언해야 한다.

## 노드 스펙

| 필드 | 필수 | 의미 |
|---|---|---|
| `id` | ✅ | 노드 식별자. `runs/<run-id>/<id>/`가 산출물 경로가 된다 |
| `skill` | ✅ | 실행할 스킬. `skills/<name>` 또는 `inline` |
| `role` | ✅ | 수행 역할. **구체 agent를 직접 쓰지 않는다** — `roles.json`이 바인딩 |
| `runtime` | ✅ | 어느 LLM에서 도는가 (`claude`·`codex`·`host`). `null`이면 `roles.json`의 active_profile 바인딩 사용. 노드별 override용 |
| `tier` | ✅ | 성능 등급 (`T1`·`T2`·`T3`). `null`이면 바인딩 사용. **runtime과 별개 축이다** — 한 필드에 섞지 않는다 |
| `_routing` | — | 해석된 라우팅 주석 (`role → runtime/tier → 모델 · agent`). **손으로 쓰지 않는다** — `harness graph --sync`가 채우고 lint가 드리프트를 잡는다 |
| `requires` | ✅ | 최소 적합성 레벨 (L0/L1/L2). 못 채우면 강등 사다리 |
| `inputs` | ✅ | 선행 노드 id 배열. 빈 배열이면 시작 노드. **같은 inputs를 가진 노드는 병렬** |
| `output_contract` | ✅ | `contracts/*.schema.json`. 종료 시 검증 |
| `gate` | — | `user-approval` 이면 사용자 승인 전까지 후행 노드 정지 |
| `retry` | ✅ | `{max, on[]}` — `contract_violation`·`verdict_request_changes`·`error` |
| `on_failure` | ✅ | `halt` / `degrade` / `skip` |
| `timeout_sec` | ✅ | 초과 시 `on_failure` 정책 적용 |
| `fanout` | — | 동적 병렬. `{from, key, role_from, roles}` — 선행 노드 산출물의 배열로 노드를 복제 |

### `fanout` 하위 필드

| 필드 | 필수 | 의미 |
|---|---|---|
| `from` · `key` | ✅ | 어느 선행 노드의 어느 배열로 복제하는가 |
| `role_from` | ✅ | 복제된 노드의 role을 배열 원소의 **어느 필드**에서 읽는가. 없으면 role이 미정의가 된다 |
| `roles` | ✅ | role 후보 목록. 정적 검증(존재 여부·라우팅 해석)의 근거다 |

> 티켓 접두사(BE/FE/DB/INFRA)로 role을 유추하지 않는다 — `DB`는 mysql/mongodb, `INFRA`는 kafka/redis로 갈려 1:1이 아니다. 산출물이 role을 직접 실어야 한다 (`contracts/design-doc.schema.json`의 `tickets[].role`).

## 두 개의 호출 경로

노드를 실제로 부르는 주체는 둘이다. **상태 기계는 둘 다 같은 경로로 결과를 받는다** — 계약 검증을 건너뛰는 경로는 없다 ([ADR 0005](../docs/decisions/0005-dispatcher-execution-layer.md)).

| 경로 | 무엇으로 부르나 | 언제 |
|---|---|---|
| **디스패처** (`harness run dispatch`) | 헤드리스 CLI subprocess (`claude -p` · `codex exec`) | 무인 병렬 실행. wave 폭이 기계로 강제된다 |
| **메인 세션** (`harness run next` → `invoke`) | Agent 툴 / 수동 | 컨텍스트를 물려받아야 할 때. 어댑터 없는 런타임(`host`) |

조립 규칙의 정본은 `orchestration/runner/adapters/*.toml` 하나다 — `harness role` 의 `invoke` 문자열도 거기서 파생된다.

## 실행 — `harness run`

그래프를 실제로 돌리는 것은 `bin/harness run` **상태 기계**다. LLM 호출은 하지 않는다 — 무엇을 실행할지 알려주고, 결과를 계약으로 검증하고, 상태를 기록한다. 호출은 메인 세션이 한다 ([ADR 0003](../docs/decisions/0003-graph-run-state-machine.md)).

```bash
bin/harness run new <graph.json> [--objective T] [--level L1|L2] [--profile P]
bin/harness run next | status                     # 열린 노드 + invoke / 전체 현황
bin/harness run dispatch [--dry-run] [--max-parallel N] [--only a,b] [--no-failover]
                                                  # ready 노드를 실제로 병렬 실행
bin/harness run wave [<fanout-node>] --repo PATH [--plan-only] [--allow-overlap]
                                                  # 티켓 fanout 을 워크트리로 갈라 실행
bin/harness run done <node> --result <file.json>  # 계약 검증 후 완료 기록
bin/harness run done <node> --result F --rework "implement[BE-01]"   # 재작업 대상 좁히기
bin/harness run gate <node> --approve | --reject "<사유>"
bin/harness run fail <node> --reason T --kind error|contract_violation
bin/harness run budget                            # 런타임 사용량·게이트 현황
bin/harness run budget --approve | --reject       # 예산 초과 시 프로파일 전환 결정
```

### 상태 파일

```
runs/<run-id>/
  state.json            # 노드별 status·attempts·degraded·gate (정본)
  journal.jsonl         # run-created·node-done·fanout·gate·request-changes 이벤트 append
  <node>/result.json    # 계약 통과한 산출물
```

노드 status: `pending` · `expanded`(fanout 부모) · `awaiting-gate` · `completed` · `failed` · `skipped`.

### 실행 규칙

- **재개 가능하다.** `state.json`이 정본이므로 세션이 끊겨도 `run status`로 이어서 진행한다. 완료 노드는 다시 열리지 않는다.
- **계약 위반은 완료가 아니다.** `run done`이 검증에 실패하면 결과를 기록하지 않고 `retry.on`에 따라 `pending`(재시도) 또는 `failed`로 남긴다.
- **강등을 기록한다.** `--level L1`로 L2 노드를 돌리면 해당 노드에 `degraded`가 박히고 `run status`·`run next`가 매번 보여준다.
- **wave 순서는 티켓 DAG에서 만든다.** fanout 자식의 의존은 `depends_on`을 그대로 옮긴 것이다 — 선행 티켓이 끝나기 전에 후행이 열리지 않는다.
- **암묵적 축소 금지.** 스킵·실패는 `journal.jsonl`에 사유와 함께 남는다. 런타임 전환으로 제거된 키(`keys-dropped`)와 페일오버 hop(`failover`)도 이벤트로 남는다.
- **병렬은 이제 기계가 강제한다.** `run dispatch` 가 같은 wave 를 ThreadPool 로 동시에 띄운다. `hooks/lib/wave-audit.py` 는 회귀 확인용으로 남는다 — 1차 방어선이 아니다.
- **런타임 쿼터가 마르기 전에 갈아탄다.** ready 노드가 쓸 런타임의 사용량이 `roles.json#runtime_budget` 임계(codex 주간 80%)를 넘으면 디스패치를 멈추고 전환을 묻는다 ([ADR 0004](../docs/decisions/0004-runtime-budget-failover.md)).

## 그래프 목록

| 파일 | 대응 스킬 | 요구 레벨 |
|---|---|---|
| `private-feature.json` | `/private-feature` 풀 파이프라인 | L2 (L1 강등 가능) |

## 실행 계층

`orchestration/runner/` 가 정본이다 ([README](./runner/README.md)) — 어댑터 스키마·프롬프트 조립·페일오버·워크트리 규칙.

```
harness test                 # tests/*.py 전량 (exit 1 = 실패)
harness run dispatch --dry-run   # 실행 없이 디스패치 계획만
```

## 라우팅 확인

노드가 **어느 LLM·어느 모델로 도는지**는 `roles.json`의 active_profile이 정하고, 그래프는 `_routing` 주석으로 그 결과를 드러낸다. 노드에 `runtime`/`tier`를 하드코딩하면 프로파일 전환(`claude-only`·`portable`)이 무력화되므로, **override는 그 노드만 예외일 때**만 쓴다.

```bash
bin/harness graph                          # active_profile 기준 노드별 라우팅 표
bin/harness graph --profile claude-only    # 다른 프로파일로 해석했을 때
bin/harness graph --sync                   # 그래프의 _routing 주석 갱신
```

### 사용량 예산 — 런타임 페일오버

codex 는 주간 쿼터를 쓴다. run 중간에 마르면 설계·리뷰 노드가 멈추고 리셋까지 최대 7일 묶인다. 그래서 **임계에 닿으면 남은 run 을 `claude-only` 로 넘긴다** ([ADR 0004](../docs/decisions/0004-runtime-budget-failover.md)).

```bash
bin/harness usage                          # 런타임별 사용량·임계 (exit 1 = 초과)
bin/harness usage codex --json
```

| 항목 | 동작 |
|---|---|
| 임계 | `roles.json#runtime_budget.codex.threshold_percent` — 주간 80% |
| 감지 시점 | `run next`·`run done`·`run new` 가 ready 셋을 계산할 때. 그 런타임을 쓰는 ready 노드가 있을 때만 조회한다 |
| 차단 | `budget_gate` 가 `pending` 인 동안 invoke 를 출력하지 않는다 |
| 승인 | `run budget --approve` → `state.profile` 을 `claude-only` 로. **완료 노드는 그대로**, 남은 노드부터 적용 |
| 반려 | `run budget --reject` → 현행 유지. 사용량이 5%p 더 오르면 다시 묻는다 |
| 소스 | `~/.codex/sessions/**/rollout-*.jsonl` 의 `rate_limits` (codex CLI 에 조회 명령 없음). `HARNESS_CODEX_USAGE_PERCENT` 로 override |

## 검증

```bash
bin/harness lint    # role·contract 실재, DAG 순환, requires 정합,
                    # 바인딩 값(runtime/tier/모델), fanout role_from·roles, _routing 드리프트
```
