# PR 작성 가이드

## 원칙

- 티켓 1개 = 브랜치 1개 = PR 1개
- Draft PR로 시작, 리뷰 준비 완료 시 Ready for Review 전환
- PR 생성 전 Hook이 자동으로 테스트 + 셀프리뷰 실행 (settings.json)

→ PR 생성·Draft 전환·머지 후 Jira 전이는 `pr-create` 스킬을 사용합니다.

---

## 브랜치 네이밍

```
<type>/<티켓접두사>-<번호>[-<short-description>]
```

type 은 다음 중 하나:

| 작업 성격 | type |
|----------|------|
| 신규 기능 | `feat` |
| 버그 수정 | `fix` |
| 동작 변경 없는 코드 개선 | `refactor` |
| 빌드·설정·의존성·문서 | `chore` |

- 티켓 접두사: `GRT`가 주로 쓰이지만 고정은 아닙니다. 프로젝트에 따라 다른 접두사도 허용.
- `short-description` 은 선택 사항. 케밥케이스(소문자·하이픈) 사용.

예시:
```
feat/GRT-7100
feat/GRT-7100-add-rental-api
fix/GRT-7101
refactor/GRT-7102-extract-payment-service
chore/GRT-7103
fix/ABC-42
```

**base 브랜치**: `dev` (main 직접 push 금지)

---

## PR 템플릿

레포마다 `.github/pull_request_template.md`가 있으며, `gh pr create` 시 자동으로 적용된다.

**표준 템플릿 (greeting 메인 레포 기준)**:

```markdown
### 개요
<!-- Jira 티켓 링크 포함 -->

- Jira: https://doodlin.atlassian.net/browse/GRT-XXXX
- (한 줄 설명 — 무엇을 왜 수정했는지)

### 작업 내용
<!-- no-jira 작업의 경우 내용 필수 -->
<!-- Jira 본문에 내용이 있다면 간략하게 작성 -->

- (핵심 변경사항 bullet, 1~3줄)

### 체크리스트
<!-- 필요에 따라 항목 추가/수정/삭제 -->
- [ ] 빌드 확인
- [ ] 테스트 통과

### 연관된 backend application
<!-- 해당 PR 내용에 영향받는 backend application -->

### 추가 유의사항
<!-- 리뷰어나 배포 시 반드시 알아야 할 사항 -->
```

**개요·작업 내용 작성 규칙:**
- 개요: Jira 링크 + 한 줄 설명을 함께 작성한다.
- 작업 내용: Jira에 내용이 있어도 핵심 변경사항을 bullet 1~3줄로 간략히 작성한다.
- 장황한 설명, 변경 파일 목록, 구현 상세 나열 금지 — 리뷰어는 diff를 직접 읽는다.

---

## PR 제목 컨벤션

```
[GRT-XXXX] - {type} : {제목}
```

| type | 용도 |
|------|------|
| `feat` | 신규 기능 |
| `fix` | 버그 수정 |
| `refactor` | 동작 변경 없는 코드 개선 |
| `chore` | 빌드·설정·의존성 변경 |
| `deploy` | 배포 관련 작업 |
| `db` | 스키마 마이그레이션 |
| `docs` | 문서 수정 |

예시:
```
[GRT-7100] - feat : 지원자 일괄 불합격 처리 API 추가
[GRT-7101] - fix : 결제 웹훅 타임아웃 예외 처리
[GRT-7102] - refactor : ApplicantService 도메인 서비스 분리
[GRT-7103] - db : applicants 테이블 rejected_at 컬럼 추가
```

---

## Hook 동작 (자동 강제)

`git push` 시:
1. `push-test.sh` — 변경 모듈 테스트 실패 → push deny
2. `push-review.sh` — Must Fix 발견 → push deny

`gh pr create` 시:
- agent hook — diff 전체 리뷰, Must Fix → PR 생성 deny

deny 시 지적 항목 수정 후 재시도. **`--no-verify` 절대 금지.**
