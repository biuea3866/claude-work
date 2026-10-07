---
name: private-implement
description: 개인 프로젝트 경량 파이프라인 — 설계 문서 없이 티켓·요구사항을 교차 런타임 TDD로 구현한다. 컨텍스트 이중 분석(A‖B) → RED(B) → GREEN/REFACTOR(A) → 결정적 게이트 → 교차 리뷰(B, 재작업 최대 2회, p0~p3 0건) → draft PR → 회고 → (사용자 확인 후) 머지. 작은 기능·버그 수정·단일 도메인 변경용. PRD·설계·티켓 분해가 필요한 본격 기능은 /private-feature.
user-invocable: true
requires: L1
roles: [analyze.context, analyze.cross, test.red, implement.be, implement.fe, implement.mysql, implement.mongodb, implement.kafka, implement.redis, review.code, review.infra]
---

요구사항: $ARGUMENTS

현재 디렉토리: !`pwd`
개인 프로젝트 마커: !`[ -f "$(git rev-parse --show-toplevel 2>/dev/null)/.claude/private-project" ] && echo "OK" || echo "없음 — 개인 프로젝트가 아니면 이 파이프라인을 쓰지 않는다"`

라우팅 (roles.json active_profile 해석):
!`~/.harness/bin/harness role --compact analyze.context analyze.cross test.red implement.be implement.fe implement.mysql implement.mongodb implement.kafka implement.redis review.code review.infra`

---

## 실행 규약

단계는 **role** 로만 지정한다. 구체 agent·모델·런타임은 `roles.json` 이 정한다 — 스킬에 하드코딩하지 않는다.

- 위 라우팅 표의 `invoke` 를 **그대로** 실행한다. `claude/*` 는 `Agent(...)`, `codex/*` 는 Bash 로 `codex exec`(페르소나를 프롬프트 앞에 주입).
- `codex exec` 는 별도 세션이라 컨텍스트를 물려받지 않는다 — **입력·산출 경로와 계약을 프롬프트에 전부 적고**, 최종 메시지는 `-o <run-dir>/<파일>` 로 받는다.
- codex 는 서브에이전트를 스폰할 수 없다(L1) — 병렬은 메인 세션이 소유한다.
- 이하 **A** = `implement.*` 런타임, **B** = A 와 다른 런타임. 어느 쪽이 claude/codex 인지는 바인딩이 정한다. 교차 불변식(RED≠GREEN, 리뷰≠GREEN, 분석 A≠B)은 `roles.json#verifies` 로 선언돼 `harness lint` 가 강제한다.
- 라우팅 표에서 위 불변식이 깨져 있으면(같은 런타임) **진행하지 않고** 사용자에게 알린다. `claude-only`·`portable` 프로파일이면 교차 이점이 없다는 사실을 보고에 명시한다.

### run 디렉토리

산출물은 대상 레포가 아니라 `~/.harness/runs/private-implement/<YYYYMMDD>-<slug>/` 에 둔다 (gitignore 대상).

| 파일 | 작성 | 단계 |
|---|---|---|
| `analysis-A.md` / `analysis-B.md` | 메인 세션 (analyze.context / analyze.cross 의 최종 메시지 원문 저장) | 1 |
| `context.md` | 메인 세션 (대조·확정) | 1 |
| `red.md` | test.red | 2 |
| `review-<n>.md` | review.code | 5 |
| `retro.md` | 메인 세션 | 7 |

## Step 0 — 범위 판별 + 격리

1. 마커가 없으면 중단하고 안내한다.
2. 요구사항이 건드리는 도메인을 판별한다: BE / FE / DB(MySQL·MongoDB) / Kafka / Redis.
3. **3개 이상 도메인 또는 티켓 L 사이즈(~800줄) 초과가 예상되면** 멈추고 `/private-feature`를 제안한다 — 경량 파이프라인의 범위가 아니다.
4. `git fetch origin && git worktree add -b <type>/<티켓ID|케밥> <worktree> origin/main` — 이후 모든 단계는 이 worktree 에서만 수행한다 ([private-branch-convention](../../rules/private-branch-convention.md), 전역 §5).
5. run 디렉토리를 만든다.

## Step 1 — 컨텍스트 분석 (A ‖ B 독립)

1. **role `analyze.context`** 와 **role `analyze.cross`** 를 **한 메시지에서 동시에** 실행한다. 입력은 동일하게 티켓·요구사항 + worktree 경로뿐이다. 서로의 산출물을 알려주지 않는다.
   - 분석가는 보고서를 **최종 메시지 원문으로 반환**하고 파일을 쓰지 않는다. 메인 세션이 그 원문을 가공 없이 `analysis-A.md` / `analysis-B.md` 로 저장한다 (codex 는 `-o` 산출, claude 는 Agent 반환값). claude 서브에이전트의 run 디렉토리 Write 가 정책으로 거부돼 매번 실패 왕복이 생겼기 때문이다 (`skills/learned/20261007-subagent-report-write-blocked.md`).
2. 메인 세션이 두 분석을 대조해 차이를 3유형으로 분류한다.

| 유형 | 예 | 처리 |
|---|---|---|
| 사실 차이 | 호출처 3곳 vs 4곳 | 코드를 직접 읽어 `파일:라인` 근거로 판정 |
| 설계 선택 차이 | 검증을 Entity vs DomainService | 컨벤션이 정하면 컨벤션. 없으면 A 안 채택 + p4 기록 (차단 아님) |
| 요구사항 해석 차이 | "중복"의 기준이 사용자 vs payload | **사용자 게이트** |

3. **사용자 게이트** — 해석 차이 또는 어느 한쪽이라도 미결 사항이 있으면 AskUserQuestion 으로 묻고 멈춘다. 답을 받기 전에 다음 단계로 가지 않는다.
4. `context.md` 를 확정한다: 수정 범위 · 레이어별 공개 계약 · 테스트 케이스 · **사용자 확정 사항**(게이트 답변 + 해소된 차이 목록).

## Step 2 — 선행 인프라 (해당 시)

테이블·컬렉션·토픽·키 변경이 포함되면 RED 보다 먼저, 서로 독립이면 **한 메시지에서 동시 실행**:

- **role `implement.mysql`** / **role `implement.mongodb`** / **role `implement.kafka`** / **role `implement.redis`**
- 완료 후 **role `review.infra`** — REQUEST_CHANGES면 담당 작업자 수정 → 재리뷰 통과까지.

## Step 3 — RED (B)

- **role `test.red`** — 입력: `context.md` 경로 + worktree. 산출: 테스트 + 스텁 + RED 커밋 + `red.md`.
- 메인 세션이 `red.md` 를 검증한다: 모든 실패 원인이 **미구현**이어야 한다. 컴파일 에러·fixture·환경 오류가 섞여 있으면 RED 로 인정하지 않고 재실행시킨다.
- `RED_SHA` 와 테스트 경로 목록을 기록한다.

## Step 4 — GREEN → REFACTOR (A)

- BE: **role `implement.be`** / FE: **role `implement.fe`** — 둘 다면 BE 먼저(API 계약 확정 후 FE).
- 입력: `context.md` + `RED_SHA` + worktree. 작업자 본문의 **교차 TDD 모드**로 동작한다 (RED 생략, GREEN → REFACTOR).
- **테스트 이의**가 보고되면 구현을 멈추고 이의 표를 들고 Step 3 으로 반려한다. 이 반려는 리뷰 재작업 횟수에 세지 않는다. 같은 이의가 2번 왕복하면 사용자에게 판정을 요청한다.
- 완료 후 기계 검사 — 테스트 diff = 0:

```bash
git -C <worktree> diff --stat <RED_SHA> -- <테스트 경로들>   # 출력이 비어 있어야 한다
```

출력이 있으면 GREEN 이 테스트를 바꾼 것이다. 변경을 되돌리게 하고 필요한 변경이면 테스트 이의로 돌린다.

## Step 5 — 결정적 게이트

LLM 리뷰 전에 기계 판정만으로 거른다. 레포의 lint·test·build 명령을 순서대로 실행하고 **exit code 로 판정**한다 (파이프로 exit code 를 가리지 않는다 — `set -o pipefail`).

- 예: Kotlin `./gradlew ktlintCheck detekt test build` / FE `pnpm lint && pnpm test && pnpm build`
- lint 자동 수정을 했다면 테스트를 다시 돌린다.
- 실패 → Step 4 로 되돌린다. 이 루프는 리뷰 재작업 횟수에 세지 않는다. 3회 연속 실패하면 사용자에게 보고한다.

## Step 6 — 교차 리뷰 (B) ⟲ 재작업 최대 2회

- **role `review.code`** — 새 세션. 입력은 **티켓·요구사항 + `context.md` 의 사용자 확정 사항 섹션만 + `origin/main...HEAD` diff**. A 의 분석 문서(`analysis-A.md`)와 `context.md` 전문은 주지 않는다 — 독립 해석이 리뷰의 가치다. 사용자 확정 사항만 주는 이유는 이미 결정된 것을 다시 다투지 않게 하기 위해서다.
- 리뷰어에게 p0~p5 와 별도로 **"해석 차이"** 섹션을 요구한다 (Step 1 의 3유형으로 분류).
- 산출: `review-<n>.md`. 메인 세션이 첫 줄에 리뷰한 커밋을 기록한다: `reviewed_sha: <git -C <worktree> rev-parse HEAD>` — Step 9 머지 게이트의 근거다.

**통과 기준: p0~p3 0건.** p4·p5 는 PR 본문에 남긴다. 이 기준이 머지 게이트(`private-auto-merge-gate.sh`, p0~p3 반영)와 같아서, 통과한 PR 은 재리뷰 없이 머지할 수 있다.

지적 라우팅:

| 지적 | 돌아갈 단계 | 테스트 |
|---|---|---|
| 동작·스펙 결함 | Step 3 (재현 테스트 추가) → 4 → 5 → 6 | 추가만 |
| 테스트 자체 결함 (구현 상세 의존) | Step 3 → 4 → 5 → 6 | 수정 허용, 사유 기록 |
| 설계·레이어·컨벤션 위반, 품질(p2) | Step 4 (REFACTOR) → 5 → 6 | 변경 금지 |
| nit(p3)만 남음 | Step 4 (REFACTOR) → 5 → 6 | 테스트 품질 지적이면 수정 허용, 사유 기록 |
| 해석 차이 — 사용자 확정 사항과 충돌 | 확정 사항 우선, 지적 기각 + 기록 | — |
| 해석 차이 — 새 해석 문제 | 사용자 게이트 | — |

- **재작업은 최대 2회**다 (리뷰 최대 3회). 지적이 p3 뿐인 회차의 반영은 재작업 횟수에 세지 않는다 — 단 p3 만으로 2회 연속 돌면 멈추고 사용자에게 남길지 묻는다. 3번째 리뷰에도 p0~p2 가 남으면 멈추고 사용자에게 에스컬레이션한 뒤 Step 8 로 간다 (실패 회고).
- 진동 감지: 같은 파일·라인에 상반된 지적이 2회 나오면 횟수와 무관하게 멈추고 사용자에게 판정을 요청한다.

## Step 7 — draft PR

[private-pr-guide](../../rules/private-pr-guide.md) 를 따른다. 교차 리뷰(Step 6)가 셀프 리뷰 게이트를 충족한다.

```bash
git -C <worktree> push -u origin <branch>   # tests-passed
gh pr create --draft --base main --title "[<티켓ID|NO-TICKET>] - <type> : <제목>" --body-file <run-dir>/pr-body.md   # self-review-done
```

- `# tests-passed` 는 Step 5 의 exit 0 raw 출력이 있을 때만 붙인다 — 없으면 거짓 단언이다.
- 본문 "검증"에 Step 5 결과, "추가 유의사항"에 잔여 p4·p5 와 교차 리뷰 회차를 적는다.
- PR URL 을 `<run-dir>/pr.txt` 에 저장한다 — Step 9 가 run 디렉토리를 찾는 키다.

## Step 8 — 회고 (통과·실패 모두)

통과했을 때뿐 아니라 **에스컬레이션·루프 상한 도달로 실패했을 때도** 회고한다. 실패가 가장 많이 배울 수 있는 사례다. PR 을 막지 않도록 Step 7 이후에 수행한다.

1. `retro.md` 에 기록한다:
   - 결과(통과 / 에스컬레이션), 리뷰 회차, 테스트 이의 왕복 수, 결정적 게이트 실패 수
   - Step 1 분석 차이 사례 (유형별)
   - 리뷰 지적 등급·유형 분포
   - 개선 태그: `#<짧은-케밥>` (예: `#red-fixture-error`, `#context-missed-callsite`)
2. 같은 태그를 이전 회고에서 찾는다: `grep -rl '#<태그>' ~/.harness/runs/private-implement/*/retro.md`
3. **2회 이상 반복된 태그만** 스킬·에이전트 수정 제안으로 올린다 — `~/.harness/skills/learned/<YYYYMMDD>-<태그>.md` 에 근거 run 목록 + 수정안. 1회성은 기록만 한다.
4. 제안은 **사용자 승인 후에만** 반영한다. 반영은 대상 레포 PR 과 섞지 않고 `~/.harness` 에서 별도로 한다 (규칙 원본은 `~/.harness`, 생성물 직접 수정 금지).


## Step 9 — 머지 (사용자 확인 후)

draft PR 을 사용자가 확인하고 머지를 지시했을 때만 수행한다. 새 세션이면 `grep -l <PR URL> ~/.harness/runs/private-implement/*/pr.txt` 로 run 디렉토리를 찾는다. 별도 리뷰 스킬을 거치지 않는다 — Step 6 통과가 머지 게이트다.

1. 마지막 `review-<n>.md` 가 통과(p0~p3 0건)인지, 그 `reviewed_sha` 가 PR HEAD 와 같은지 확인한다:

```bash
gh pr view <PR> --json headRefOid,isDraft -q .headRefOid   # reviewed_sha 와 같아야 한다
```

2. 다르면 리뷰 이후 검증되지 않은 커밋이 있는 것이다. 머지하지 않고 Step 5 → 6 을 다시 돈다 (재작업 횟수와 별개).
3. 같으면 draft 를 해제하고 머지한다. 토큰의 근거는 `review-<n>.md` 다 — 근거 없이 붙이면 거짓 단언이다.

```bash
gh pr ready <PR>
gh pr merge <PR> --squash --delete-branch   # p3-reflected
```

4. 머지 raw 출력을 `retro.md` 끝에 덧붙이고 worktree 를 정리한다 (`git worktree remove <worktree>`).

## 보고

> 완료 단언은 `rules/COMPLETION-RULE.md` §1~4를 모두 충족해야 한다.

```
## /private-implement 결과: {in-progress | 완료 | 에스컬레이션}
- 런타임: A={runtime} / B={runtime} (프로파일 {active_profile})
- worktree: {경로} / run: {run 디렉토리}
- 분석 차이: 사실 {n} · 설계 {n} · 해석 {n} (사용자 게이트 {n}회)
- RED: {RED_SHA}, 테스트 이의 {n}회
- 결정적 게이트: {명령 + exit code raw 출력}
- 리뷰: {회차}회, 최종 verdict {..}, reviewed_sha {sha}, 잔여 p4·p5 {n}건
- draft PR: {URL}
- 머지: {대기 (사용자 확인 필요) | squash 머지 raw 출력}
- 회고: {retro.md 경로}, 스킬 수정 제안 {있음/없음}
```
