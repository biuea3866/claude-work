# docs — 서술적 맥락 (3개 영역)

규범이 아니다. 지켜야 할 것은 `rules/`와 `policy.json`에 있고, 여기에는 **왜 그렇게 됐는지**와 **무엇이 어디 있는지**를 둔다.

| 영역 | 내용 |
|---|---|
| [architecture/](./architecture/) | 하네스가 어떻게 조립되는가 — 데이터 흐름·실행 흐름·층별 존재 이유 |
| [decisions/](./decisions/) | ADR — 왜 그렇게 정했는가. 번호 순서로 누적하고 지우지 않는다 |
| [external/](./external/) | 외부 자료·링크 |

## 단독 문서

| 파일 | 내용 |
|---|---|
| [ssot-map.md](./ssot-map.md) | 정보 → 정본 위치. "이건 어디서 고치나"의 답 |
| [onboarding.md](./onboarding.md) | 새 머신에서 하네스 복원 (clone → link → build → doctor) |

## ADR 목록

| # | 제목 | 상태 |
|---|---|---|
| [0001](./decisions/0001-harness-as-ssot.md) | 하네스를 `~/.harness` 단일 진실 원천으로 분리 | 채택 |
| [0002](./decisions/0002-llm-runtime-routing.md) | 노드별 LLM 런타임 배정 (claude ↔ codex 교차 리뷰) | 채택·반영 완료 |
| [0003](./decisions/0003-graph-run-state-machine.md) | 그래프 실행을 LLM 밖의 상태 기계로 분리 | 채택·반영 완료 · 0005 로 부분 개정 |
| [0004](./decisions/0004-runtime-budget-failover.md) | codex 주간 사용량 상한 도달 시 claude 로 페일오버 | 채택·반영 완료 |
| [0005](./decisions/0005-dispatcher-execution-layer.md) | 실행 계층(디스패처) 신설 — ready 노드를 실제 병렬 실행 | 채택·반영 완료 |

## 작성 규칙

- **ADR은 시점 기록이다.** 그때의 실측치(파일 수·게이트 수)를 그대로 남긴다 — 나중에 값이 변해도 고치지 않는다. 대신 상태(`채택`/`대체됨`)를 갱신한다.
- **그 외 문서는 가변 카운트를 박지 않는다.** "스킬 6개" 같은 숫자는 각 디렉토리 README가 정본이고, 여기서는 참조만 한다 (측정 도구가 스스로 드리프트 원천이 되지 않게).
- 문체·용어는 [output-style](../rules/output-style.md)을 따른다.
