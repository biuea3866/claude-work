---
name: private-feature
description: 개인 프로젝트 풀 파이프라인 — PRD 작성→검수→시니어 설계(be 먼저, fe/dba 병렬)→pm 정합 검증→구현 지휘(wave 병렬)→리뷰→PR 자동머지. 요구사항 텍스트 또는 기존 PRD 경로를 인수로 받는다. 사용자 게이트 2회(PRD 승인, 설계 승인). 가벼운 작업은 /private-implement.
user-invocable: true
---

요구사항: $ARGUMENTS

현재 디렉토리: !`pwd`
개인 프로젝트 마커: !`[ -f "$(git rev-parse --show-toplevel 2>/dev/null)/.claude/private-project" ] && echo "OK" || echo "없음 — 개인 프로젝트가 아니면 이 파이프라인을 쓰지 않는다"`

---

개인 프로젝트 전용 heavy 파이프라인. 메인 세션은 오케스트레이션만 하고, 산출물은 전부 서브에이전트가 만든다. 산출물 저장 루트: `/Users/biuea/Desktop/dpdpdndn/프로젝트/{앱 카테고리}/`.

## Step 0 — 전제 확인

- 마커가 없으면 중단하고 안내한다 (`touch .claude/private-project` + 커밋).
- 앱 카테고리가 인수에서 특정되지 않으면 저장 루트의 디렉토리 목록을 보여주고 사용자에게 확인한다.
- 인수가 기존 PRD 경로면 Step 1을 건너뛰고 Step 2부터 시작한다.

## Step 1 — PRD

1. `Agent(private-prd-writer)` — 요구사항 전달. 질문 목록이 반환되면 **사용자에게 그대로 전달**하고 답변을 받아 재실행한다 (가정 금지).
2. `Agent(private-prd-reviewer)` — PRD 경로 전달. `NEEDS_REVISION`이면 지적 목록을 writer에게 넘겨 보완 → 재검수 (최대 2회, 이후 사용자 에스컬레이션).
3. **게이트 ① (사용자 승인)** — PRD 경로·Goals/Non-Goals·P0 요구사항·검수 결과를 요약 보고하고 설계 진행 승인을 받는다.

## Step 2 — 설계 (be 먼저 → fe/dba 병렬)

1. `Agent(private-senior-be)` — PRD 경로 전달. TDD + BE 티켓 + API 계약 산출.
2. senior-be 완료 후 **한 메시지에서 동시 스폰**:
   - `Agent(private-senior-fe)` — PRD + BE TDD 경로 (API 계약 소비, FE 설계 + FE 티켓)
   - `Agent(private-senior-dba)` — PRD + BE TDD 경로 (도메인 모델 소비, DB 설계) — 테이블 변경이 없으면 스킵
3. `Agent(private-senior-pm)` — 전 설계·티켓의 PRD 정합 검증. `NEEDS_REVISION`이면 지적을 해당 시니어에게 넘겨 보완 → 재검증 (최대 2회).
4. **게이트 ② (사용자 승인)** — 설계 문서 경로·채택 방안·티켓 DAG(wave 너비 분포)·무중단 배포 시나리오를 요약 보고하고 **구현 진행 승인**을 받는다. 이 승인은 구현→리뷰→PR→자동머지까지의 자동 진행을 포함한다.

## Step 3 — 구현 (승인 후 자동)

1. `Agent(private-tpm)` — 설계·티켓 전체 경로 전달. tpm이 통합 DAG 작성 후:
   - 인프라 wave: mysql/mongodb/kafka/redis implementer 스폰 → `private-infra-reviewer` 통과까지
   - BE/FE 게이트: `private-senior-be`/`private-senior-fe`에 wave 지휘 위임 (implementer 팀 병렬, wave마다 `private-code-reviewer` 통과)
2. 메인 세션은 tpm의 진행 보고(도메인 × wave × 티켓 표)를 사용자에게 중계한다. 게이트를 막는 실패는 즉시 보고.

## Step 4 — 마무리 (자동)

브랜치 전략은 [private-branch-convention](../../rules/private-branch-convention.md)을 따른다 — **`origin/main` 기준 숏텀 티켓 브랜치를 각자 `main`으로 머지**한다. 전체 기능을 하나의 장수명 피처 브랜치에 모아 마지막에 통째로 머지하지 않는다.

각 티켓 브랜치마다 (senior가 wave 지휘 중 순차 처리):
1. 변경 모듈 테스트를 실제 실행해 exit 0 확인 후 push — `git push ... # tests-passed`.
2. `gh pr create --base main` 로 PR 생성 (제목: `[티켓ID] - <type> : 제목`, 본문: PRD·TDD 링크 + 변경 요약).
3. `Agent(private-code-reviewer)` — PR 재리뷰. p0~p3 전부 반영 확인 시 리뷰어가 `gh pr merge --squash --auto # p3-reflected` 실행. 미반영이 있으면 담당 implementer 수정 → 재리뷰 반복. 머지 후 티켓 브랜치 삭제.
4. **`main` 머지 = dev 배포** — 여기까지가 이 파이프라인의 범위다. 여러 티켓을 원자적으로만 릴리즈해야 하는 피치 못할 경우에만 피처 브랜치를 쓰되 base는 `main`, 근거를 PR에 남긴다.

## prod 배포 (별도 요청 시)

prod 배포는 자동 진행하지 않는다 — 사용자가 요청하면 `Agent(private-qa)`를 먼저 실행한다 (dev 실구동 E2E + 회귀). **verdict PASS 없이 prod 배포 금지**, FAIL이면 버그 리포트를 담당 implementer에게 넘겨 수정 → QA 전체 재실행.

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
