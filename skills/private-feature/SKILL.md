---
name: private-feature
description: 개인 프로젝트 풀 파이프라인 — PRD 작성→검수→시니어 설계(be 먼저, fe/dba 병렬)→pm 정합 검증→구현 지휘(wave 병렬)→리뷰→PR 자동머지. 요구사항 텍스트 또는 기존 PRD 경로를 인수로 받는다. 사용자 게이트 2회(PRD 승인, 설계 승인). 가벼운 작업은 /private-implement.
user-invocable: true
requires: L2
roles: [prd.author, prd.review, design.be, design.fe, design.db, design.review, plan.coordinate, implement.be, implement.fe, implement.mysql, implement.mongodb, implement.kafka, implement.redis, review.code, review.infra, qa]
---

요구사항: $ARGUMENTS

현재 디렉토리: !`pwd`
개인 프로젝트 마커: !`[ -f "$(git rev-parse --show-toplevel 2>/dev/null)/.claude/private-project" ] && echo "OK" || echo "없음 — 개인 프로젝트가 아니면 이 파이프라인을 쓰지 않는다"`

라우팅 (roles.json active_profile 해석):
!`~/.harness/bin/harness role --compact prd.author prd.review design.be design.fe design.db design.review plan.coordinate implement.be implement.fe review.code review.infra qa`

---

## 실행 규약 (모든 단계 공통)

단계는 **role** 로만 지정한다. 구체 agent·모델·런타임은 `roles.json` 이 정한다 — 스킬에 하드코딩하지 않는다.

- 위 라우팅 표의 `invoke` 를 **그대로** 실행한다. `claude/*` 는 `Agent(...)`, `codex/*` 는 Bash 로 `codex exec`(페르소나를 stdin 으로 주입).
- 표에 없는 role 이 필요하면 `~/.harness/bin/harness role <role>` 로 해석해 쓴다. 임의로 agent 를 고르지 않는다.
- `codex exec` 는 별도 세션이라 컨텍스트를 물려받지 않는다 — **입력 파일 경로·산출 경로·계약을 프롬프트에 전부 적는다.** 산출물은 파일로 받고, 경로를 다음 단계 프롬프트에 넘긴다.
- `<worktree>` 는 그 단계가 작업할 디렉토리다 (문서 단계는 산출물 저장 루트, 구현 단계는 해당 티켓 worktree).
- codex 는 서브에이전트를 스폰할 수 없다(L1). **wave 병렬·fanout 은 메인 세션이 소유**하고, codex 단계는 단발 호출로 소비한다.

## 실행 상태 관리 (runs/)

상태는 **메인 세션이 기억하지 않는다** — `~/.harness/bin/harness run` 이 소유한다. 어느 노드가 열렸는지·계약을 통과했는지는 `runs/<run-id>/state.json` 이 정본이다.

| 시점 | 명령 |
|---|---|
| 시작 | `~/.harness/bin/harness run new orchestration/private-feature.json --objective "<앱 카테고리> / <기능명>" --level <L1\|L2>` |
| **무인 병렬 실행 (기본)** | `~/.harness/bin/harness run dispatch` — 열린 노드를 **실제로 동시 실행**하고 계약 검증까지 자동 ([ADR 0005](../../docs/decisions/0005-dispatcher-execution-layer.md)) |
| 실행 계획만 확인 | `~/.harness/bin/harness run dispatch --dry-run` — LLM 호출 0 |
| 티켓 wave (구현 단계) | `~/.harness/bin/harness run wave --repo <대상 레포> [--plan-only]` — 티켓별 워크트리 확보 후 병렬 |
| 손으로 부를 때 | `~/.harness/bin/harness run next` — 열린 노드와 그 `invoke` 를 그대로 실행 |
| 단계 완료 (손으로 부른 경우) | `~/.harness/bin/harness run done <node> --result <runs/.../result.json>` |
| 사용자 게이트 | `~/.harness/bin/harness run gate <node> --approve` / `--reject "<사유>"` |
| 실패 | `~/.harness/bin/harness run fail <node> --reason "<사유>" --kind <error\|contract_violation>` |
| 재개·현황 | `~/.harness/bin/harness run status` |
| 런타임 예산 게이트 | `~/.harness/bin/harness run budget --approve` / `--reject` |

- **계약 위반이면 `run done` 이 거부된다.** 지적을 담당 role 에게 넘겨 보완한 뒤 다시 보고한다 — 조용히 통과시키지 않는다.
- 리뷰가 `REQUEST_CHANGES` 면 `retry.to` 대상이 자동 재개방된다. 한 티켓만 재작업하면 `--rework "implement[BE-01]"` 로 좁힌다.
- **병렬은 기계가 강제한다.** `run dispatch` 가 같은 wave 를 동시에 띄운다. `run next` 로 손수 부를 때만 "한 메시지에서 동시 스폰" 규율이 필요하다 — 그때도 직렬로 흐르면 `/private-wave-audit` 이 사후에 잡는다.
- 티켓 fanout·wave 순서는 `plan` 산출물의 `depends_on` 에서 엔진이 만든다 — 순서를 손으로 관리하지 않는다.
- **`host` 런타임 노드는 디스패처가 실행하지 않는다** (부를 subprocess 가 없다). `run dispatch` 가 "수동 실행 필요"로 보고하면 현재 세션에서 직접 수행하고 `run done` 으로 보고한다.
- **같은 wave 의 티켓 소유 경로가 겹치면 `run wave` 가 실행 전에 막는다** — 병렬 실행이 곧 머지 충돌이다. 티켓을 다른 wave 로 나눈다.
- **런타임 예산 게이트가 뜨면 디스패치를 멈춘다.** codex 주간 사용량이 80% 를 넘으면 `run next` 가 invoke 대신 게이트를 출력한다. 사용자에게 사용량·리셋 시각과 "전환 시 교차 리뷰 이점을 잃는다"는 트레이드오프를 보고하고 `--approve`(남은 노드를 claude-only 로) / `--reject`(현행 유지) 를 받는다. 임의로 결정하지 않는다 ([ADR 0004](../../docs/decisions/0004-runtime-budget-failover.md)).

개인 프로젝트 전용 heavy 파이프라인. 메인 세션은 오케스트레이션만 하고, 산출물은 전부 서브에이전트가 만든다. 산출물 저장 루트: `/Users/biuea/Desktop/dpdpdndn/프로젝트/{앱 카테고리}/`.

## Step 0 — 전제 확인

- 마커가 없으면 중단하고 안내한다 (`touch .claude/private-project` + 커밋).
- 앱 카테고리가 인수에서 특정되지 않으면 저장 루트의 디렉토리 목록을 보여주고 사용자에게 확인한다.
- 인수가 기존 PRD 경로면 Step 1을 건너뛰고 Step 2부터 시작한다.

## Step 1 — PRD

1. **role `prd.author`** — 요구사항 전달. 질문 목록이 반환되면 **사용자에게 그대로 전달**하고 답변을 받아 재실행한다 (가정 금지).
2. **role `prd.review`** — PRD 경로 전달. `NEEDS_REVISION`이면 지적 목록을 writer에게 넘겨 보완 → 재검수 (최대 2회, 이후 사용자 에스컬레이션).
3. **게이트 ① (사용자 승인)** — PRD 경로·Goals/Non-Goals·P0 요구사항·검수 결과를 요약 보고하고 설계 진행 승인을 받는다.

## Step 2 — 설계 (be 먼저 → fe/dba 병렬)

1. **role `design.be`** — PRD 경로 전달. TDD + BE 티켓 + API 계약 산출.
2. senior-be 완료 후 **동시 실행** (`run dispatch` 가 두 노드를 함께 띄운다. 손으로 부르면 한 메시지에서 동시 스폰):
   - **role `design.fe`** — PRD + BE TDD 경로 (API 계약 소비, FE 설계 + FE 티켓)
   - **role `design.db`** — PRD + BE TDD 경로 (도메인 모델 소비, DB 설계) — 테이블 변경이 없으면 스킵
3. **role `design.review`** — 전 설계·티켓의 PRD 정합 검증. `NEEDS_REVISION`이면 지적을 해당 시니어에게 넘겨 보완 → 재검증 (최대 2회).
4. **게이트 ② (사용자 승인)** — 설계 문서 경로·채택 방안·티켓 DAG(wave 너비 분포)·무중단 배포 시나리오를 요약 보고하고 **구현 진행 승인**을 받는다. 이 승인은 구현→리뷰→PR→자동머지까지의 자동 진행을 포함한다.

## Step 3 — 구현 (승인 후 자동)

1. **role `plan.coordinate`** — 설계·티켓 전체 경로 전달. tpm이 통합 DAG 작성 후:
   - `run wave --repo <대상 레포> --plan-only` 로 티켓 wave 분포·소유 충돌을 먼저 확인한다. 모든 wave 너비가 1~2면 직선형 DAG — 분해 실패이므로 재분해를 senior 에게 돌린다.
   - `run wave --repo <대상 레포>` 로 티켓별 워크트리를 확보하고 wave 단위 병렬 실행한다. 인프라 티켓(`implement.mysql`/`mongodb`/`kafka`/`redis`)이 선행 wave에 오도록 `depends_on` 이 잡혀 있어야 한다.
   - wave 마다 role `review.code`(코드) / `review.infra`(인프라) 게이트를 통과시킨다. `REQUEST_CHANGES` 면 엔진이 `retry.to` 를 재개방한다.
2. 메인 세션은 tpm의 진행 보고(도메인 × wave × 티켓 표)를 사용자에게 중계한다. 게이트를 막는 실패는 즉시 보고.

## Step 4 — 마무리 (자동)

브랜치 전략은 [private-branch-convention](../../rules/private-branch-convention.md)을 따른다 — **`origin/main` 기준 숏텀 티켓 브랜치를 각자 `main`으로 머지**한다. 전체 기능을 하나의 장수명 피처 브랜치에 모아 마지막에 통째로 머지하지 않는다.

각 티켓 브랜치마다 (senior가 wave 지휘 중 순차 처리):
1. 변경 모듈 테스트를 실제 실행해 exit 0 확인 후 push — `git push ... # tests-passed`.
2. `gh pr create --base main` 로 PR 생성 (제목: `[티켓ID] - <type> : 제목`, 본문: PRD·TDD 링크 + 변경 요약).
3. **role `review.code`** — PR 재리뷰. p0~p3 전부 반영 확인 시 리뷰어가 `gh pr merge --squash --auto # p3-reflected` 실행. 미반영이 있으면 담당 implementer 수정 → 재리뷰 반복. 머지 후 티켓 브랜치 삭제.
4. **`main` 머지 = dev 배포** — 여기까지가 이 파이프라인의 범위다. 여러 티켓을 원자적으로만 릴리즈해야 하는 피치 못할 경우에만 피처 브랜치를 쓰되 base는 `main`, 근거를 PR에 남긴다.

## prod 배포 (별도 요청 시)

prod 배포는 자동 진행하지 않는다 — 사용자가 요청하면 **role `qa`**를 먼저 실행한다 (dev 실구동 E2E + 회귀). **verdict PASS 없이 prod 배포 금지**, FAIL이면 버그 리포트를 담당 implementer에게 넘겨 수정 → QA 전체 재실행.

## 완료 보고

> 완료 단언은 `rules/COMPLETION-RULE.md` §1~4를 모두 충족해야 한다.

```
## /private-feature 결과: {in-progress | 완료}
- PRD / TDD / 설계 / 티켓: {경로들}
- 구현: {wave × 티켓 완료 표}
- 리뷰: {verdict 이력}
- PR: {URL, 머지 여부 + raw 출력}
- 미해결: {있으면}
```
