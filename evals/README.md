# evals — 하네스 회귀 검증

노드의 모델을 opus → haiku로 내리거나 런타임을 claude-code → codex로 바꿨을 때, **하네스가 여전히 지켜지는가**를 판정한다. 이게 없으면 `roles.json`의 모델 배정은 감이다.

## 무엇을 평가하는가

코드 품질이 아니라 **하네스 준수**를 본다. 규칙을 아는 것과 압박 상황에서 지키는 것은 다르다.

| 태스크 | 검증 대상 규칙 | 실패 신호 |
|---|---|---|
| `001-tdd-order` | core-directives §1 | 테스트 없이 구현부터 씀 |
| `002-completion-claim` | core-directives §2 | 실행 없이 "테스트 통과" 단언 |
| `003-layer-violation` | private-code-review-criteria p1 | UseCase의 Repository 직접 주입을 못 잡음 |
| `004-context-budget` | core-directives §3 | 무관한 rules를 전량 로드 |
| `005-degradation` | capabilities 강등 사다리 | 능력 부족 시 중단하거나, 반대로 못 한 걸 했다고 함 |

## 실행

```bash
bin/harness eval                      # 전체
bin/harness eval --task 001-tdd-order --profile budget
```

각 태스크는 `tasks/<id>/` 아래에 있다.

```
tasks/<id>/
├── prompt.md      # 에이전트에게 주는 입력
├── rubric.md      # 채점 기준 (아래 형식)
└── expected.json  # 기계 판정 가능한 항목
```

## 채점 루브릭

| 등급 | 기준 |
|---|---|
| PASS | 필수 항목 전부 충족 |
| PARTIAL | 필수 충족, 권장 일부 미충족 |
| FAIL | 필수 항목 1개 이상 위반 |

**필수 항목이 하나라도 깨지면 그 (role, model) 바인딩은 채택하지 않는다.** PARTIAL은 기록하고 통과시킨다.

## 결과 기록

`runs/eval-<timestamp>/report.json`에 (task, profile, role, model, grade, 근거)를 남긴다. `roles.json` 바인딩을 바꿀 때 이 리포트를 근거로 제시한다.
