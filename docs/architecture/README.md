# docs/architecture — 시스템 구조 서술

하네스가 **어떻게 조립되는가**를 서술한다. 규범이 아니다 — 지켜야 할 것은 `rules/`와 `policy.json`에 있다.

## 데이터 흐름

```
policy.json ─┐
rules/       ├─→ bin/harness build ─→ adapters/<runtime>/ ─→ 런타임 네이티브 설정
roles.json  ─┘                                                (settings.json · config.toml · hooks.json)

~/.harness/{rules,agents,skills,commands,hooks,mcp}
        └─(심링크)─→ ~/.claude/… , ~/.codex/…
```

## 실행 흐름

```
사용자 요청
  → 런타임(메인 세션 주도 에이전트)
  → HARNESS.md 진입 절차 (레벨 판정 → 코어 지침 → 선택 규칙 로드)
  → skills/ 또는 orchestration/ 그래프
  → 노드마다 roles.json이 (agent, runtime, tier, exec.access) 바인딩 — harness role/graph 로 해석
  → harness run dispatch 가 ready 노드를 실제 병렬 실행 (orchestration/runner/ + adapters/*.toml)
     · 티켓 fanout 은 harness run wave 가 워크트리로 갈라 실행
     · 메인 세션이 Agent 툴로 직접 부르는 경로도 그대로 유효 (ADR 0005)
  → 산출물은 contracts/ 스키마 + 의미 규칙 검증 후 runs/<run-id>/ 기록
  → hooks/가 게이트 강제 (훅 미지원 런타임은 절차 강제로 강등)
```

## 왜 이 층들이 필요한가

| 층 | 없으면 생기는 일 |
|---|---|
| `policy.json` | 런타임마다 권한 설정이 따로 놀아 드리프트 |
| `roles.json` | 스킬이 구체 agent·모델에 결합 → 런타임 교체 불가, 교차 리뷰 성립 안 함 |
| `contracts/` | 노드 모델 교체가 곧 품질 사고 |
| `capabilities.md` | "어느 LLM이든"이 검증 불가능한 구호로 남음 |
| `evals/` | 모델 배정이 근거 없는 감 |
| `runs/` | 재개·감사·핸드오프 불가 |

## 문서

- [decisions/](../decisions/) — 왜 그렇게 정했는가 (ADR)
- [external/](../external/) — 외부 자료

## 설계 문서

| 파일 | 내용 | 상태 |
|---|---|---|
| [20260827-multiagent-runner-tdd.md](./20260827-multiagent-runner-tdd.md) | 실행 계층 신설 — 선언만 있는 그래프를 실제 병렬 실행으로. `gitkraken-clone-app/.agent/orchestration` 이식 | **반영 완료** → [ADR 0005](../decisions/0005-dispatcher-execution-layer.md) |
