---
description: 티켓 DAG를 위상정렬해 wave 단위로 병렬 구현한다 (티켓당 워크트리 1개 + 프로세스 1개). 실행 전 wave 계획·소유 경로 교집합을 검증하고 사용자 확인 후에만 실제 실행한다. 명시 호출 전용 — 티켓 N건 × 유료 호출.
requires: L2
roles: [implement.be, implement.fe, implement.mysql, implement.mongodb, implement.kafka, implement.redis]
---

# /private-ticket-wave — 티켓 wave 병렬 구현

인수: `$ARGUMENTS` — 대상 레포 경로 / `--fanout <노드>` / `--wave-only` 등. 없으면 되묻는다.

라우팅 (roles.json active_profile 해석):
!`~/.harness/bin/harness role --compact implement.be implement.fe implement.mysql implement.kafka`

현재 run 현황:
!`~/.harness/bin/harness run status 2>&1 | head -20`

---

## 세 진입점의 관계 — 포함이 아니라 형제

```
harness run dispatch      워크플로우 노드 폭   → 스레드 병렬 (같은 wave 노드 N개)
/private-ticket-wave      티켓 폭             → 프로세스 + 워크트리 병렬 (티켓 N개)
/private-feature          파이프라인 전체       → 위 둘을 순서대로 부른다
```

서로를 호출하지 않는다. 같은 상태 기계를 **다른 폭**으로 부른다.

- 기능 하나를 처음부터 끝까지 → `/private-feature`
- 이미 `plan` 이 끝난 run 의 **구현 단계만** → 본 커맨드
- 노드 하나만 → `harness run dispatch --only <노드>`

## 선행 조건 (하나라도 없으면 중단)

| 조건 | 확인 | 없으면 |
|---|---|---|
| 진행 중인 run | `harness run status` | 아래 **Step 0** 으로 만든다 |
| `plan` 노드 완료 | 같은 출력의 `plan` 이 `completed` | 티켓 목록이 없다 — Step 0 |
| 대상 레포 경로 | 사용자 인수 | **되묻는다.** 추측하지 않는다 — 엉뚱한 레포에 워크트리를 만든다 |
| `claude`·`codex` CLI | `command -v` | 디스패처가 실행 불가. 사용자에게 보고한다 |

**run 이 이미 있으면 그 `repo` 를 확인한다.** `harness run status` 는 최신 run 을 집으므로,
남의 run(검증용·다른 기능)을 이어받을 수 있다. `run wave` 출력의 `대상 레포` 가 의도한 경로가
아니면 멈추고 사용자에게 묻는다 — `--repo` 로 덮거나 새 run 을 만든다.

## Step 0 — run 확보 (두 경로)

### (a) 티켓 md 가 이미 있다 → 브릿지

PRD·설계·티켓을 이미 손으로 썼으면 파이프라인을 처음부터 돌리지 않는다.

```bash
# ① 티켓 md → plan 산출물 (계약 검증까지, LLM 호출 0)
~/.harness/bin/harness plan from-tickets <티켓 디렉토리> --out /tmp/plan.json

# ② 그 plan 으로 run 을 앞당긴다 (PRD·설계 노드를 preauthored 로 기록)
~/.harness/bin/harness run new orchestration/private-feature.json \
  --objective "<앱 카테고리> / <기능명>" --level L2 --seed-plan /tmp/plan.json
```

`plan from-tickets` 가 읽는 것:

| 무엇 | 어디서 |
|---|---|
| 티켓 id·제목 | `<PREFIX>-NN-<슬러그>.md` 파일명 + `# [ID] 제목` |
| 의존 | 각 티켓의 `## 의존` 섹션 — **정본** |
| 소유 경로 | `_분해-DAG.md` 의 `\| ID \| \`경로\` \|` 표 |
| role | 접두사(BE/FE) 또는 본문 근거(DB→mysql/mongodb, INFRA→kafka/redis) |

**추측하지 않는다** — 소유 경로가 없으면 실패하고(Single Writer 검증 입력), DB·INFRA 의 role
근거가 없으면 `--role ID=role` 로 지정하라고 요구한다.

> 분해 DAG 문서가 선언한 wave 분포와 티켓 `## 의존` 이 어긋나면 **의존이 이긴다.**
> 그 차이를 사용자에게 보고한다 — 문서 쪽 오류일 수 있다.

### (b) 기획부터 시작한다 → 파이프라인

`/private-feature <요구사항>` 으로 PRD·설계·plan 까지 진행한 뒤 본 커맨드로 돌아온다.

## Step 1 — 계획 검증 (필수, 무료)

```bash
~/.harness/bin/harness run wave --repo <대상 레포> --plan-only
```

출력에서 확인할 것 — 하나라도 어긋나면 **실행하지 않고** 사용자에게 보고한다:

| 출력 | 뜻 |
|---|---|
| 티켓 wave 구성·너비 | 의도한 병렬 폭인가 |
| `대상 밖 의존 — 이미 완료로 간주` | 그 선행 티켓이 **정말** 끝났는가 |
| `모든 wave 너비가 1~2` 경고 | 직선형 DAG = 분해 실패. `plan.coordinate` 에 재분해를 돌린다 |
| `소유 경로 교집합` | 같은 wave 두 티켓이 같은 파일을 쓴다 — **분해를 고친다** |
| 워크트리 루트·브랜치 | 만들어질 경로가 맞는가 |

소유 교집합은 `--allow-overlap` 으로 뚫을 수 있지만 **머지 충돌을 감수한다는 선언**이다.
사용자가 명시하지 않으면 쓰지 않는다.

## Step 2 — 사용자 확인

계획을 그대로 게시하고 확인을 받는다. 게시할 내용:

- 대상 레포 · 워크트리 루트 · 브랜치 접두
- 티켓 wave 구성 (너비 포함)
- **동시에 뜰 프로세스 수** (= 첫 wave 너비) 와 각 티켓의 role·모델
- 예상 비용 근거 (티켓 수 × 노드 최소 소요)

## Step 3 — 드라이런 (유료 실행 직전, 무료)

```bash
~/.harness/bin/harness run wave --repo <대상 레포> --dry-run
```

워크트리를 만들지 않고 자리표시자·페르소나 파일·계약 경로까지 검증한다. LLM 호출 0.
여기서 걸리면 실행에서도 걸린다 — 반드시 통과시킨 뒤 넘어간다.

## Step 4 — 실제 실행

```bash
~/.harness/bin/harness run wave --repo <대상 레포> [--max-parallel 4]
```

- `--max-parallel` — 티켓 **내부** 노드 폭. 티켓 수 상한이 아니다
- `--branch-prefix` 기본 `feat`, `--base` 기본 `origin/main` ([private-branch-convention](../rules/private-branch-convention.md))
- **출력을 `| tail` 로 가리지 않는다** — 파이프는 끝 명령의 exit code 만 남겨 실패를 가린다
  ([COMPLETION-RULE](../rules/COMPLETION-RULE.md) §2)

실행기가 하는 일:

1. wave 전량의 소유 교집합을 **실행 전에** 재검사 (설계 검증 이후 늘어난 파일을 잡는다)
2. wave 전원의 워크트리를 **순차로** 확보 (`git worktree add` 는 동시 실행에 안전하지 않다)
3. ready 티켓을 **동시에** 디스패치
4. 결과를 `run done`/`run fail` 과 **같은 경로**로 커밋 — 계약 검증을 건너뛰지 않는다

## Step 5 — 결과 처리

| 상황 | 처리 |
|---|---|
| 전 티켓 completed | 다음 wave 를 위해 다시 본 커맨드를 부른다 (ready 자식만 열린다) |
| 계약 위반 | `run done` 이 거부했다. 지적을 담당 role 에게 넘겨 보완 → 재실행. **조용히 통과시키지 않는다** |
| `REQUEST_CHANGES` | 엔진이 `retry.to` 를 재개방한다. 한 티켓만 좁히려면 `run done <node> --rework "implement[BE-01]"` |
| 실패 | `harness run status` 로 사유를 읽고 사용자에게 보고. `on_failure=halt` 면 후행은 열리지 않는다 |
| 런타임 소진 | 어댑터가 1 hop 전환한다. 제거된 키가 journal 에 남으므로 산출물 품질 저하 여부를 확인한다 |

진행 보고는 `harness run status` 를 도메인 × wave × 티켓 표로 사용자에게 중계한다.

## 하지 않는 것

- ❌ 자동 발화 — 티켓 N건 × 유료 호출이므로 **명시 호출 전용**
- ❌ 대상 레포·티켓을 추측해서 채우기
- ❌ Step 1 계획 검증 없이 실행
- ❌ 소유 교집합을 `--allow-overlap` 으로 임의 통과
- ❌ 직선형 DAG 경고를 무시하고 진행
- ❌ 워크트리 삭제 (`git worktree remove`) — 사람의 미커밋 변경이 사라진다
- ❌ 게이트 도달을 실패로 보고
- ❌ push·PR·머지 — 그건 `/private-feature` 리뷰·머지 단계와 훅의 몫이다
- ❌ 남의 run 을 대상 레포 확인 없이 이어받기 — `run status` 는 최신 run 을 집는다
- ❌ 이미 구현·머지된 티켓을 다시 돌리기 — 대상 레포의 브랜치·PR 상태를 먼저 확인한다

## 완료 보고

> 완료 단언은 [COMPLETION-RULE](../rules/COMPLETION-RULE.md) §1~4 를 모두 충족해야 한다.

```
## /private-ticket-wave 결과: {in-progress | 완료}
- 대상 레포 / 워크트리 루트: {경로}
- 티켓 wave: {너비 분포} · 이번에 실행한 wave: {N}
- 결과: {티켓별 status 표 + 계약 통과 여부}
- 비용: {누적 $}
- 미해결: {있으면}
```

## 관련

- `harness plan from-tickets` — 티켓 md → plan 산출물 (Step 0-a)
- `harness run dispatch` — 노드 폭 실행
- [private-feature](../skills/private-feature/SKILL.md) — 파이프라인 전체
- [orchestration/runner/README.md](../orchestration/runner/README.md) — 실행기 옵션·워크트리 규칙
- [private-ticket](../rules/private-ticket.md) — 티켓 분해·Single Writer·fan-out 게이트
