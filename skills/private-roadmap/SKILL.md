---
name: private-roadmap
description: 개인 프로젝트 과제 발굴·구체화 파이프라인 — 경쟁사·고객 요구 조사(A‖B 교차 런타임) → 출처 교차 검증 → 신규 아이디어 발굴(A‖B) → 로드맵(우선순위·도메인별 목표) → PRD 단위 과제 분리 → 과제별 PRD 구체화 → PRD 리뷰 → 과제 간 충돌 검증 → 과제 확정. 리뷰 지적 유형별로 해당 단계로 루프백(최대 2회). 사용자 게이트 2회(로드맵 승인, 과제 확정). 확정 PRD 는 /private-feature 설계 단계로 넘긴다.
user-invocable: true
requires: L2
roles: [research.market, research.cross, research.verify, idea.generate, idea.cross, roadmap.author, roadmap.split, roadmap.review, prd.author, prd.review]
---

입력 (앱 카테고리 / 주제 / 대상 제품 설명 / 경쟁사 후보·고객 요구 문서·회사 로드맵 경로 — 뒤 셋은 선택): $ARGUMENTS

현재 디렉토리: !`pwd`
프로젝트 카테고리 목록: !`ls -1 /Users/biuea/Desktop/dpdpdndn/프로젝트/ 2>/dev/null || echo "(디렉토리 없음)"`

라우팅 (roles.json active_profile 해석):
!`~/.harness/bin/harness role --compact research.market research.cross research.verify idea.generate idea.cross roadmap.author roadmap.split roadmap.review prd.author prd.review`

---

## 실행 규약

단계는 **role** 로만 지정한다. 구체 agent·모델·런타임은 `roles.json` 이 정한다 — 스킬에 하드코딩하지 않는다.

- 위 라우팅 표의 `invoke` 를 **그대로** 실행한다. `claude/*` 는 `Agent(...)`, `codex/*` 는 Bash 로 `codex exec`(페르소나를 stdin 으로 주입).
- `codex exec` 는 별도 세션이라 컨텍스트를 물려받지 않는다 — **입력 파일 경로·산출 경로·mode·출력 형식을 프롬프트에 전부 적는다.** 산출물은 파일로 받는다.
- invoke 의 `<worktree>` 는 `<run-dir>` 이다 — codex 샌드박스(workspace-write)는 `-C` 밖에 쓰지 못한다. PRD 단계는 PRD 저장 디렉토리(카테고리 루트)를 넘긴다.
- **A‖B 단계는 한 메시지에서 동시 실행**한다 (claude 는 Agent, codex 는 background Bash). 한쪽이 끝나기를 기다렸다 다른 쪽을 부르면 독립성은 유지돼도 병렬이 깨진다.
- A‖B 산출물은 **서로에게 넘기지 않는다** — 교차 검증 단계 전까지 독립이어야 편향이 드러난다.
- 이후 단계(리뷰·PRD 작성)에는 조사 원문 대신 `04-roadmap-summary.md` 를 넘긴다 — 컨텍스트 예산.
- 런타임 예산 게이트(codex 주간 80%)가 뜨면 멈추고 사용자에게 묻는다. 전환하면 A‖B·교차 리뷰가 같은 런타임이 되어 이 파이프라인의 전제가 약해진다는 점을 함께 보고한다.

## 산출물

저장 루트: `/Users/biuea/Desktop/dpdpdndn/프로젝트/{앱 카테고리}/roadmap/{YYYYMMDD}-{주제}/` (이하 `<run-dir>`)

| 파일 | 단계 | 작성 role |
|---|---|---|
| `00-input.md` | 0 | 메인 세션 |
| `01-research-A.md` · `01-research-B.md` | 1 | `research.market` · `research.cross` |
| `02-verified.md` | 2 | `research.verify` |
| `03-ideas-A.md` · `03-ideas-B.md` | 3 | `idea.generate` · `idea.cross` |
| `04-roadmap.md` · `04-roadmap-summary.md` · `04-roadmap-review.md` | 4 | `roadmap.author` · `roadmap.review` |
| `05-tasks.md` · `05-tasks-review.md` | 5 | `roadmap.split` · `roadmap.review` |
| 과제별 PRD | 6 | `prd.author` — 경로·파일명은 `rules/private-prd-template.md` 저장 규칙 |
| `07-portfolio-review.md` | 7 | `roadmap.review` |
| `08-confirmed.md` | 8 | 메인 세션 |

## Step 0 — 입력 확정

1. 앱 카테고리가 인수에 없으면 위 목록을 보여주고 사용자가 지정하게 한다. 임의로 새 카테고리를 만들지 않는다.
2. 대상 제품·주제가 모호하면 스폰 전에 질문한다 (가정 금지).
3. 고객 요구 소스는 **사용자 제공 문서**와 **웹 공개 리뷰** 두 가지다. 사내·비공개 데이터는 쓰지 않는다.
4. **회사 로드맵은 조사 대상이 아니라 제약 조건**이다. 경로가 있으면 `00-input.md` 에 "제약"으로 기록한다.
5. `<run-dir>/00-input.md` 에 위 내용을 기록한다.

## Step 1 — 시장 조사 (A‖B 동시)

- **role `research.market`** → `01-research-A.md`, **role `research.cross`** → `01-research-B.md`. 입력은 둘 다 `00-input.md` 하나.

## Step 2 — 교차 검증

- **role `research.verify`** — A·B 경로 전달 → `02-verified.md`.
- `재조사 요청` 이 있으면 해당 role(A/B)에 요청 표만 넘겨 보완 조사 → 재검증 (최대 2회). 2회 후에도 남으면 `미검증` 으로 두고 진행한다.

## Step 3 — 신규 아이디어 (A‖B 동시)

- **role `idea.generate`** → `03-ideas-A.md`, **role `idea.cross`** → `03-ideas-B.md`. 입력은 `02-verified.md` + `00-input.md`.
- 경쟁사·고객 요구에서 바로 나오는 항목뿐 아니라, 아무도 풀지 않은 지점의 **신규 아이디어**를 가설·검증 방법과 함께 받는다.

## Step 4 — 로드맵

1. **role `roadmap.author`** (mode `roadmap`) — `02-verified.md` · `03-ideas-A/B.md` · `00-input.md` 전달 → `04-roadmap.md` + `04-roadmap-summary.md`.
2. **role `roadmap.review`** (mode `roadmap`) → `04-roadmap-review.md`. NEEDS_REVISION 이면 아래 **루프백** 표대로 처리.
3. **게이트 ① (사용자 승인)** — 도메인별 목표 · 우선순위 상위 10개 · 아이디어 판정(채택 신규 아이디어 강조) · 회사 로드맵 충돌을 요약 보고하고 승인을 받는다. 우선순위는 사업 판단이므로 LLM 결과를 그대로 확정하지 않는다.

## Step 5 — 과제 분리 (PRD 단위)

1. **role `roadmap.split`** (mode `split`) — 승인된 `04-roadmap.md` 전달 → `05-tasks.md`.
2. **role `roadmap.review`** (mode `split`) → `05-tasks-review.md`. NEEDS_REVISION 이면 루프백.

## Step 6 — 과제별 PRD 구체화 → 리뷰

과제마다 아래를 수행한다. 과제끼리는 독립이므로 **동시 실행**한다 (codex 는 background Bash 여러 개).

1. **role `prd.author`** — `05-tasks.md` 의 해당 과제 + `04-roadmap-summary.md` 전달. 프롬프트에 다음을 명시한다:
   - 구조·문체는 `rules/private-prd-template.md` 그대로 (개조식 명사형). Overview 의 Epic/과제 ID·근거 문서에 과제 ID·근거 로드맵 항목을, 인사이트의 참조 제품 표에 `02-verified.md` 의 확인 사실을 쓴다.
   - 사용자 문제 → 해결 방안 표의 사용자 문제 열에 As-Is, 세부 정책(User Story + AC · As-Is/To-Be · 상세 정책)에 To-Be 세부 정책을 쓴다.
   - Target release 는 로드맵 단계(분기) 단위까지만 — 날짜 일정은 설계 이후에 정한다.
   - `# Roadmap Alignment` 섹션을 Open Questions 앞에 추가해 다른 과제·도메인·회사 로드맵과의 의존·충돌 가능성을 적는다.
2. **role `prd.review`** — PRD 경로 + `04-roadmap-summary.md` 전달. NEEDS_REVISION 이면 지적을 writer 에게 넘겨 보완 (최대 2회).

## Step 7 — 과제 간 충돌 검증

- **role `roadmap.review`** (mode `portfolio`) — 모든 PRD 경로 + `04-roadmap-summary.md` + `05-tasks.md` 전달 → `07-portfolio-review.md`.
- 과제를 하나씩 리뷰해서는 PRD 간 중복·정책 충돌이 보이지 않는다. 이 단계를 생략하지 않는다.

## 루프백 — 지적 유형별 재작업

리뷰(`roadmap.review`·`prd.review`) 지적의 유형이 돌아갈 단계를 정한다. 원인이 앞 단계에 있으면 가장 앞 단계로 간다.

| 유형 | 돌아갈 단계 | 재실행 범위 |
|---|---|---|
| `fact` | Step 2 교차 검증 | 해당 사실 재검증 → 그 사실을 쓴 로드맵 항목·과제·PRD 만 재작성 |
| `idea` | Step 3 아이디어 | 해당 아이디어 재발굴 → Step 4 부터 |
| `priority` | Step 4 로드맵 | 로드맵 재작성 → 게이트 ① 재승인 → 영향받는 과제만 Step 5 부터 |
| `boundary` | Step 5 과제 분리 | 과제 재분리 → 바뀐 과제만 Step 6 부터 |
| `policy` | Step 6 PRD | 해당 PRD 만 재작성 → 재리뷰 → Step 7 |

- **같은 단계로의 루프백은 최대 2회**다. 이후에도 지적이 남으면 멈추고 사용자에게 에스컬레이션한다 (지적 목록 + 시도 이력).
- 루프백마다 `<run-dir>/loop-log.md` 에 `회차 · 유형 · 대상 단계 · 지적 요약` 을 1줄씩 남긴다.
- 지적 유형 판정은 리뷰어가 한다. 메인 세션이 유형을 바꾸지 않는다.

## Step 8 — 과제 확정

- **게이트 ② (사용자 승인)** — 과제 목록 · 각 PRD 경로 · prd.review / portfolio verdict · 남은 Open Questions · 루프 이력을 보고하고 확정 승인을 받는다.
- 승인되면 `08-confirmed.md` 에 확정 과제·PRD 경로·의존 순서를 기록한다.
- 다음 단계 안내: 과제마다 `/private-feature <PRD 경로>` — 기존 PRD 경로를 받으면 Step 1(PRD)을 건너뛰고 설계부터 시작한다. `depends_on` 순서를 지킨다.

## 완료 보고

> 완료 단언은 `rules/COMPLETION-RULE.md` §1~4를 모두 충족해야 한다.

```
## /private-roadmap 결과: {in-progress | 완료}
- run-dir: {경로}
- 조사: 확인 사실 {n} · 고객 요구 {n} · 재조사 {n}회
- 신규 아이디어: A {n} / B {n} → 채택 {n} (신규 {n})
- 로드맵: 도메인 {n} · 게이트 ① {승인 일시}
- 과제(PRD): {과제 ID · PRD 경로 · prd.review verdict} 표
- 포트폴리오 검증: {verdict}
- 루프백: {유형별 횟수}
- 다음: /private-feature {PRD 경로} ({depends_on 순서})
```
