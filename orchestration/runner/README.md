# orchestration/runner — 실행 계층

그래프의 **선언**을 실제 프로세스로 바꾸는 층. `bin/harness run` 이 "무엇을 실행할 차례인가"를
정하고, 여기가 "그것을 실제로 부른다".

근거: [ADR 0005](../../docs/decisions/0005-dispatcher-execution-layer.md).
이식 원본: `gitkraken-clone-app/.agent/orchestration/runner`.

```
orchestration/runner/
├── README.md            # 본 문서
├── adapter.py           # CLI argv 조립 · 소진 감지 · failover 변환 · 접근 등급 번역
├── dispatch.py          # 프롬프트 조립 · subprocess 실행 · wave 병렬
├── wave.py              # 티켓 DAG 위상정렬 · Single Writer 검사 · 워크트리 확보
└── adapters/            # 런타임 선언 (TOML) — 새 런타임은 여기 1개만 추가
    ├── README.md
    ├── claude.toml
    └── codex.toml
```

## 층 경계 — 무엇이 무엇을 모르는가

| 층 | 아는 것 | 모르는 것 |
|---|---|---|
| `bin/harness run` | ready 셋 · 계약 · 게이트 · 재시도 · journal | argv · 프로세스 · 벤더 |
| `dispatch.py` | 프롬프트 조립 · 프로세스 수명 · 병렬 폭 | 무엇을 실행할 차례인가 |
| `adapter.py` | argv 조립 규칙 · 소진 패턴 | 노드 · 상태 · 계약 |
| `wave.py` | 티켓 의존 · 소유 경로 · 워크트리 | LLM 호출 |

두 축을 섞으면 프로파일 전환과 런타임 추가가 서로를 막는다. 러너 코드에 **런타임 이름 분기는
없다** — 전부 `adapters/*.toml` 선언이다.

## 실행

```bash
harness run dispatch [--dry-run] [--max-parallel N] [--only a,b] [--no-failover] [--set K=V]
harness run wave [<fanout-node>] [--repo PATH] [--worktree-root P] [--branch-prefix feat]
                 [--base origin/main] [--plan-only] [--allow-overlap] [--dry-run]
```

- `dispatch` — ready 노드를 동시에 실행하고 결과를 `run done`/`run fail` 과 **같은 경로**로
  상태 기계에 되먹인다. 계약 검증을 건너뛰지 않는다.
- `wave` — fanout 자식(티켓)을 티켓별 워크트리에 배치하고 wave 단위로 실행한다.

## 실행 전 전수 검증 (조용한 오염 차단)

노드를 하나라도 실행하기 전에 아래를 전부 본다. 하나라도 걸리면 **0개 노드 실행**이다.

| 검사 | 없으면 생기는 일 |
|---|---|
| 미치환 `{{자리표시자}}` | 노드가 그 문자열을 요구사항으로 읽는다 |
| 선행 노드 산출물 파일 부재 | 노드가 "파일이 없다"고만 적고 추측으로 채운다. 산출물은 멀쩡해 보인다 |
| 페르소나 파일 부재 | 역할 규범 없이 돈다 |
| 런타임 어댑터 부재 | 실행 불가 |
| 같은 wave 소유 경로 교집합 (`wave`) | 병렬 실행이 곧 머지 충돌 |
| 기준 ref 부재 (`wave`) | 티켓이 엉뚱한 커밋 위에 얹힌다 |

## 프롬프트 4부 구성

`dispatch.build_prompt` 가 만든다. 런타임마다 다른 조립을 하지 않는다 — 그러면 산출물이
런타임에 따라 달라진다.

| 섹션 | 내용 |
|---|---|
| `# 역할` | `agents/<agent>.md` 전문 (codex 는 서브에이전트가 없어 프롬프트로 주입) |
| `# 작업` | 노드 `prompt` + `--set` 치환 |
| `# 입력` | 선행 산출물 **경로** 목록 + "추측하지 마세요" |
| `# 출력 계약` | `output_contract` 스키마 + JSON 단독 출력 지시 |

## 환경 변수 — `[env]`

어댑터가 자식 프로세스 환경을 선언한다. 부모 셸은 건드리지 않는다.

claude 어댑터가 `ANTHROPIC_API_KEY` 를 지우는 이유: 그 키가 있으면 CLI 가 claude.ai 로그인
대신 키를 쓰고, 키에 크레딧이 없으면 **모든 claude 노드가 실패**한다 (2026-08-27 실측).

## 두 층의 페일오버

**같은 것이 아니다.** 둘 다 필요하다.

| 층 | 시점 | 판정 | 동작 |
|---|---|---|---|
| 예산 게이트 ([ADR 0004](../../docs/decisions/0004-runtime-budget-failover.md)) | run 중 ready 계산 시 | 누적 사용량 ≥ 임계 | 디스패치 중단, 사용자에게 프로파일 전환 승인 요청 |
| 노드 페일오버 (여기) | 노드가 실제로 죽은 뒤 | 어댑터 `exhaustion_patterns` 정규식 | 대체 런타임으로 **1 hop** 재시도 |

1 hop 제한 이유: claude → codex → claude 순환을 막고, 양쪽 모두 소진된 상황에서 무한 재시도로
시간을 태우지 않기 위해서다. 전환 시 미지원 키는 제거되며 **제거 사실이 로그와 journal 에 남는다** —
조용히 사라지면 산출물 품질이 떨어진 이유를 알 수 없다.

## 교차 검증 — 정적 + 실행 시점 2중

검증자와 피검증자가 같은 런타임이면 같은 맹점을 공유한다. 정적 검사만으로는 페일오버가 이를 우회한다.

| 층 | 근거 | 위반 시 |
|---|---|---|
| `harness lint` | `roles.json#roles[].verifies` 정적 바인딩 | 오류 |
| `build_node_spec` | 피검증자의 `runtime_used` (실제 실행 런타임) | 검증자 런타임 재배정 (tier 유지) |
| 재배정 불가 | 피검증자가 모든 런타임을 사용 | 디스패치 중단 · 사용자 결정 필요 |
| `run_node` failover | `_forbidden_runtimes` | 그 런타임으로 전환하지 않는다 |

재배정·차단은 journal 에 `cross-review-reroute` · `cross-review-blocked` 로 남는다.

## 워크트리 규칙

- 티켓별 전용 트리: `<repo-parent>/<repo>-worktrees/<ticket>` (`--worktree-root` 로 변경)
- 브랜치: `<prefix>/<ticket-id>`, base 는 `origin/main` ([private-branch-convention](../../rules/private-branch-convention.md))
- **`git worktree remove` 를 호출하지 않는다** — 사람의 미커밋 변경을 지울 수 있다. 이미 있으면 재사용한다.
- `git worktree add` 는 동시 실행에 안전하지 않다 — 스폰 전에 **순차로** 확보하고 실행만 병렬로 간다.

## 동시성 규칙

- 워커 스레드는 `state.json` 을 만지지 않는다. 결과는 디스패처 프로세스가 **직렬로 커밋**한다.
- 노드 재실행은 안전해야 한다 — 이전 시도의 산출물을 먼저 지우고 실행한다. 남아 있으면 실패를
  성공으로 오판한다.

## 테스트

```bash
harness test                 # tests/*.py 전량 (exit 1 = 실패)
harness test adapter wave    # 이름 부분 일치로 선택
```

`tests/test_dispatch.py` 는 가짜 CLI 스크립트를 PATH 에 올려 **실제 LLM 없이** 병렬성·failover·
타임아웃을 검증한다. 병렬성은 1초 작업 4개가 3초 미만에 끝나는지로 실증한다.
