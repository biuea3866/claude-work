# [개인] 브랜치 전략 (trunk-based / origin/main 기준)

개인 프로젝트 브랜치·머지 규칙. `private-be-implementer`·`private-fe-implementer`가 작업 기준으로, `private-senior-be`·`private-senior-fe`가 wave 지휘 기준으로, `/private-feature`·`/private-implement`·`/private-review` 스킬이 머지 기준으로 공통 참조한다 (SSOT).

## 원칙 — 숏텀 작업 브랜치 + main 머지

- **기준 브랜치는 `origin/main`.** 모든 작업 브랜치는 최신 `origin/main`에서 딴다: `git fetch origin && git worktree add -b <branch> <path> origin/main`.
- **작업 브랜치는 숏텀** — 티켓/작은 단위 하나만 담고, 완료(리뷰 통과) 즉시 `main`에 머지하고 브랜치를 삭제한다. 여러 날 끌지 않는다 (지향: 1일 이내).
- **머지 대상은 항상 `main`.** `main` 머지 = 배포 트리거 ([private-deploy-convention](./private-deploy-convention.md)).
- **피처 브랜치에 서브 브랜치를 쌓지 않는다.** 여러 티켓을 장수명 피처 브랜치에 스택하고 그 위에 서브피처 브랜치를 얹어 마지막에 피처 브랜치를 통째로 머지하는 패턴을 **금지**한다. 각 티켓은 `origin/main`에서 독립으로 따서 `main`으로 **각자** 머지한다.

## 병렬 wave에서 (senior 지휘)

- 같은 wave의 티켓은 각각 `origin/main` 기준 독립 작업 브랜치 + 전용 worktree에서 진행한다. Single Writer per File(같은 wave 두 티켓이 같은 파일 수정 금지, [private-ticket](./private-ticket.md))로 머지 충돌을 원천 차단한다.
- 티켓 완료 → 리뷰 통과 → 그 브랜치를 `main`으로 머지 → 브랜치 삭제. **wave 전체를 한 브랜치에 모았다가 통째로 머지하지 않는다.**
- 후행 wave는 선행 wave 머지로 갱신된 최신 `main`을 다시 base로 따서 시작한다.

## 브랜치 이름

- `<type>/<티켓ID>[-<케밥 설명>]` — type: `feat` / `fix` / `refactor` / `chore`. base `main`. 예: `feat/BE-03-rental-return`.
- 티켓이 없는 경량 작업(`/private-implement`)은 `<type>/<케밥 설명>`.

## 예외 — 피처/서브피처 브랜치 (피치 못할 때만)

기본은 위 숏텀 원칙이다. 아래처럼 **부분 머지가 불가능한 경우에만** 피처 브랜치를 쓰고, 그때도 근거를 PR/티켓에 남기고 최대한 짧게 유지한다.

- 여러 티켓이 하나의 원자적 릴리즈로만 의미가 있어 부분 머지 시 `main`이 깨지는 경우 — 단 **피처 플래그로 부분 머지**가 가능하면 그 방법을 우선한다 (피처 브랜치보다 우선, [private-be-code-convention](./private-be-code-convention.md) "피처 플래그").
- 외부 의존·대형 마이그레이션으로 장기간 통합이 불가능한 변경.

> 피처 브랜치를 쓰더라도 **머지 대상은 `main`** 이고, 그 위에 서브피처를 다시 스택하지 않는다.

## 배포 연계

- `main` 머지 = dev 환경 배포 트리거 ([private-deploy-convention](./private-deploy-convention.md)).
- prod 릴리즈는 `main`에서 릴리즈 태그를 따 배포한다 (`/private-release`) — QA verdict PASS가 선행 조건이다.

## 참고 문서

- [private-ticket](./private-ticket.md) — Single Writer per File·wave 분해
- [private-deploy-convention](./private-deploy-convention.md) — dev/prod 배포 진입 조건
- 전역 `CLAUDE.md` §5 — worktree 격리 (동시 세션 안전)
