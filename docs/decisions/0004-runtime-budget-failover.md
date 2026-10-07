# ADR 0004 — codex 주간 사용량 상한 도달 시 claude 로 페일오버

- **날짜**: 2026-08-14
- **상태**: 채택 · 반영 완료 (`bin/harness usage`, `bin/harness run budget`, `roles.json#runtime_budget`)
- **관련**: [ADR 0002](./0002-llm-runtime-routing.md), [ADR 0003](./0003-graph-run-state-machine.md), [orchestration/README.md](../../orchestration/README.md)

## 배경

`cross-review` 프로파일은 문서 작성·리뷰 판정 노드를 codex 에 둔다 ([ADR 0002](./0002-llm-runtime-routing.md)). 그런데 codex 는 **주간 쿼터(7일 창)** 를 쓴다. run 중간에 쿼터가 마르면:

- `codex exec` 가 429 로 떨어지고, 그 노드는 `run fail` → 재시도도 같은 이유로 실패한다.
- 파이프라인이 설계·리뷰 노드에서 멈춘다. 남은 구현 노드(claude)는 선행 의존 때문에 열리지 않는다.
- 쿼터 리셋까지 최대 7일 — run 하나가 통째로 묶인다.

즉 **가용성 문제가 라우팅 정책에 숨어 있었다.** 라우팅은 "어느 LLM 이 이 일을 잘하는가"만 봤고, "그 LLM 을 지금 쓸 수 있는가"는 보지 않았다.

## 결정

**주간 사용량이 임계(80%)에 닿으면 남은 run 을 `claude-only` 프로파일로 전환한다. 전환은 사용자 승인 게이트를 거친다.**

| 항목 | 값 | 이유 |
|---|---|---|
| 임계 | 주간 80% | 100% 소진 후 대응하면 이미 멈춘 뒤다. 남은 20% 는 orchestration 밖 단발 작업용으로 남긴다 |
| 전환 단위 | **프로파일 전체** (`claude-only`) | 노드별 런타임만 갈아끼우면 tier 의미가 깨진다. `claude-only` 는 교차 리뷰 상실을 보상하려 리뷰 노드를 T1 로 유지하도록 이미 설계돼 있다 |
| 전환 시점 | 게이트 승인 후 | 교차 리뷰 상실은 품질 트레이드오프다. 사용자가 모르는 사이에 바뀌면 안 된다 |
| 적용 범위 | **남은 노드만** | 완료 노드는 재실행하지 않는다. `state.profile` 을 바꾸면 이후 해석부터 새 프로파일이 적용된다 |
| 반려 시 | 현행 유지 + 재질문 억제 | 같은 사용량으로 매번 묻지 않는다. `re_ask_percent_step`(5%p) 만큼 더 오르면 다시 묻는다 |

## 사용량은 어디서 읽는가

codex CLI 에는 사용량 조회 명령이 **없다**(`codex --help` 기준 2026-08-14). 유일한 소스는 세션 rollout 로그다.

```
~/.codex/sessions/<YYYY>/<MM>/<DD>/rollout-*.jsonl
  → payload.type == "token_count" 이벤트의 rate_limits
     { "primary": {"used_percent": 24.0, "window_minutes": 10080, "resets_at": 1786167550},
       "secondary": null, ... }
```

- `window_minutes: 10080` = 7일 = **주간 창**. 플랜에 따라 primary 가 5시간 창이고 secondary 가 주간일 수 있어, **창이 가장 넓은 쪽**을 주간으로 본다.
- 가장 최근 로그 파일부터 훑어 **마지막 스냅샷**을 쓴다. 즉 수치는 *직전 codex 호출 시점* 기준이다 — 호출할수록 최신화되므로 orchestration 진행 중에는 충분히 신선하다.
- 로그를 못 읽는 환경(원격·CI)에서는 `HARNESS_CODEX_USAGE_PERCENT` 로 주입한다.

## 상태 기계에 붙는 방식

[ADR 0003](./0003-graph-run-state-machine.md) 원칙 그대로 — CLI 는 판단만 하고 호출하지 않는다.

```
harness run next
  → ready 셋 계산
  → ready 노드가 쓸 런타임에 예산 정책이 있으면 사용량 조회   ← 여기
  → 임계 초과면 budget_gate 를 pending 으로 열고 디스패치 중단
  → harness run budget --approve  → state.profile = claude-only
                       --reject   → 유지 (사용량이 +5%p 오르면 재질문)
```

- 조회는 **ready 노드에 해당 런타임이 실제로 있을 때만** 한다. claude 노드만 열려 있으면 codex 쿼터를 볼 이유가 없다.
- 게이트 개폐·전환은 `journal.jsonl` 에 `budget-exceeded` / `budget-switch` / `budget-declined` 로 남는다.
- `roles.json#runtime_budget.codex.gate: false` 로 두면 묻지 않고 즉시 전환한다.

## 검증

- `tests/test_runtime_budget.py` — 로그 파서(최신 파일·마지막 스냅샷·주간 창 선택·소스 부재), 정책 로드, 게이트 상태 기계(개폐·승인·반려·재질문·디스패치 차단) 28 케이스.
- `harness lint` — `runtime_budget` 의 runtime·임계 범위·fallback_profile 실재를 검사하고, **fallback 프로파일이 여전히 같은 런타임을 쓰면 오류**로 잡는다 (전환해도 사용량이 계속 느는 자기모순 방지).

## 대안과 미채택 사유

| 대안 | 미채택 사유 |
|---|---|
| 429 를 받고 나서 페일오버 | 이미 노드가 실패한 뒤다. 재시도 예산을 태우고 journal 이 실패로 더러워진다 |
| codex 노드만 claude 로 치환 (프로파일 유지) | tier 결정이 프로파일에 있는데 상태만 예외를 갖게 된다 — `harness graph` 해석과 실제 실행이 갈린다 |
| T1 codex 노드는 유지, T2/T3 만 전환 | 남은 쿼터를 계속 갉아 100% 소진 위험이 남는다. 80% 임계를 둔 목적과 충돌 |
| 자동 전환(게이트 없음) | 교차 리뷰 상실은 품질 트레이드오프다. 기본은 승인, 필요하면 `gate: false` 로 끈다 |
