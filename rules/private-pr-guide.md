---
id: private-pr-guide
title: "[개인] PR 작성 가이드"
scope: task
level: MUST
context: private
---

# [개인] PR 작성 가이드

개인 프로젝트 PR 규약. `private-be-implementer`·`private-fe-implementer`가 PR 생성 기준으로, `/private-implement`·`/private-feature`의 리뷰·머지 단계가 참조한다 (SSOT). 브랜치 이름·머지 대상은 [private-branch-convention](./private-branch-convention.md)이 정한다 — 여기에 복제하지 않는다.

## 원칙

- 티켓 1개 = 브랜치 1개 = PR 1개. base 는 `main`.
- PR 생성 전 셀프 리뷰가 선행된다 — `private-require-self-review.sh` 훅이 강제한다 (우회 토큰 `# self-review-done`).
- 머지는 리뷰(role review.code)에서 p0~p3 0건이 확인되고 그 리뷰 커밋이 PR HEAD 와 같을 때만 (`/private-implement` Step 9) — `private-auto-merge-gate.sh` 훅이 강제한다 (우회 토큰 `# p3-reflected`).
- 티켓 md 가 Source of Truth 다. PR 본문에 요구사항을 다시 쓰지 않고 **경로로 링크**한다.

## PR 제목

```
[<티켓ID>] - <type> : <제목>
```

티켓 ID 접두사는 [private-ticket](./private-ticket.md)을 따른다 (`BE`/`FE`/`DB`/`INFRA`). 티켓 없는 경량 작업(`/private-implement`)은 `[NO-TICKET]`.

| type | 용도 |
|------|------|
| `feat` | 신규 기능 |
| `fix` | 버그 수정 |
| `refactor` | 동작 변경 없는 코드 개선 |
| `chore` | 빌드·설정·의존성 변경 |
| `db` | 스키마 마이그레이션 |
| `docs` | 문서 수정 |

예시:

```
[BE-03] - feat : 대여 반납 API 추가
[FE-07] - fix : 다크 모드에서 잔액 텍스트 대비 부족 수정
[DB-01] - db : rentals 테이블 returned_at 컬럼 추가
```

## PR 본문 템플릿

```markdown
### 개요
- 티켓: {티켓 md 경로 또는 "없음 — /private-implement"}
- (한 줄 설명 — 무엇을 왜 수정했는지)

### 작업 내용
- (핵심 변경사항 bullet 1~3줄)

### 검증
- 테스트: (`./gradlew test` 등 실행 명령 + 통과 여부)
- (스키마 변경 시) 마이그레이션 적용·롤백 확인 여부

### 추가 유의사항
- (리뷰·배포 시 반드시 알아야 할 사항. 없으면 "없음")
```

**작성 규칙**

- 변경 파일 목록·구현 상세를 나열하지 않는다 — 리뷰어는 diff 를 직접 읽는다.
- "검증" 항목은 [COMPLETION-RULE](./COMPLETION-RULE.md)을 따른다. 실행하지 않은 것을 통과로 적지 않는다.
- 상태 전이·마이그레이션·파괴적 변경이 포함되면 롤백 방법을 "추가 유의사항"에 1줄 명시한다.

## 훅 동작 (자동 강제)

| 시점 | 훅 | 동작 |
|---|---|---|
| `git push` | `private-push-test.sh` | 테스트 통과 확인 없으면 차단 |
| `git push --force` | `private-block-git-push.sh` · `private-block-destructive.sh` | 승인 프롬프트 / 차단 |
| `gh pr create` | `private-require-self-review.sh` | 셀프 리뷰 미수행 시 차단 |
| `gh pr merge` | `private-auto-merge-gate.sh` | 재리뷰 p0~p3 반영 확인 전 차단 |

차단 시 지적을 수정하고 재시도한다. **`--no-verify` 는 금지**다.

## 참고 문서

- [private-branch-convention](./private-branch-convention.md) — 브랜치 이름·머지 대상·worktree
- [private-code-review-criteria](./private-code-review-criteria.md) — 리뷰 등급·verdict
- [private-ticket](./private-ticket.md) — 티켓 ID 접두사
