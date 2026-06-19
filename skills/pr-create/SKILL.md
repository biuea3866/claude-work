---
name: pr-create
description: 현재 브랜치의 PR을 생성하고 Draft→Ready 전환, 머지 후 Jira 전이까지 처리한다. Jira 티켓 번호 또는 NO-JIRA를 인수로 받는다.
model: sonnet
user-invocable: true
---

대상: $ARGUMENTS (PROJ-XXXX 티켓 번호 — Jira 티켓이 없으면 `NO-JIRA`)

현재 브랜치: !`git branch --show-current`
현재 날짜: !`date +%Y-%m-%d`

---

## Step 1 — 사전 확인

```bash
git status
git log origin/dev..HEAD --oneline
```

커밋이 없거나 origin/dev와 동일하면 중단한다.

### push (Hook 테스트 실행)

PR 생성 전 브랜치를 push한다. push 시 Hook(`push-test`/`push-review`)이 변경 모듈 테스트를 돌리므로, **프로젝트 Java 버전과 셸 `JAVA_HOME`이 일치해야 한다.** 불일치 시 gradle `Inconsistent JVM-target` 오류로 push가 거부된다.

```bash
# 프로젝트 Java 버전 확인: .sdkmanrc / .java-version / build.gradle.kts 의 jvmTarget
# 예) 프로젝트가 17이면
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
git push -u origin "$(git branch --show-current)"
```

`--no-verify`로 Hook을 우회하지 않는다.

---

## Step 2 — PR 생성

**Jira 티켓이 없으면(`NO-JIRA`) 제목 접두사를 `[NO-JIRA]`로 한다** (예: `[NO-JIRA] - refactor : 마스킹 N+1 제거`). 이때 본문 `개요`의 Jira 링크는 빼고 한 줄 설명으로 대체하며, `작업 내용`을 반드시 채운다.

`.github/pull_request_template.md`가 있으면 그대로 본문으로 사용한다:

```bash
gh pr create \
  --title "[PROJ-XXXX] - {type} : {제목}" \
  --body "$(cat .github/pull_request_template.md)" \
  --base dev \
  --draft
```

없으면 아래 표준 템플릿을 사용한다:

```markdown
### 개요
<!-- Jira 티켓 링크 포함 -->

- Jira: {ATLASSIAN_BASE_URL}/browse/PROJ-XXXX
- (한 줄 설명)

### 작업 내용
<!-- no-jira 작업의 경우 내용 필수 -->
<!-- Jira 본문에 내용이 있다면 간략하게 작성 -->

- (핵심 변경사항 bullet)

### 체크리스트
<!-- 필요에 따라 항목 추가/수정/삭제 -->
- [ ] 빌드 확인
- [ ] 테스트 통과

### 연관된 backend application
<!-- 해당 PR 내용에 영향받는 backend application -->

### 추가 유의사항
<!-- 리뷰어나 배포 시 반드시 알아야 할 사항 -->
```

**PR 제목 type 선택**

| type | 용도 |
|------|------|
| `feat` | 신규 기능 |
| `fix` | 버그 수정 |
| `refactor` | 동작 변경 없는 코드 개선 |
| `chore` | 빌드·설정·의존성 변경 |
| `deploy` | 배포 관련 작업 |
| `db` | 스키마 마이그레이션 |
| `docs` | 문서 수정 |

---

## Step 3 — Draft → Ready 전환 (선택)

리뷰 준비가 완료되었을 때 실행한다:

```bash
gh pr ready <PR번호>
```

---

## Step 4 — 머지 후 Jira 전이 (선택)

`NO-JIRA`이면 이 단계를 생략하고 로컬 브랜치 정리(`git branch -d`)만 한다.

PR 머지 후 Jira 상태를 배포 대기로 전이한다.

```bash
# transition ID 조회
curl -s "{ATLASSIAN_BASE_URL}/rest/api/3/issue/PROJ-XXXX/transitions" \
  -u "${ATLASSIAN_EMAIL}:${ATLASSIAN_API_TOKEN}" \
  | python3 -c "import json,sys; [print(t['id'], t['name']) for t in json.load(sys.stdin)['transitions']]"

# 전이 실행
curl -s -X POST \
  "{ATLASSIAN_BASE_URL}/rest/api/3/issue/PROJ-XXXX/transitions" \
  -u "${ATLASSIAN_EMAIL}:${ATLASSIAN_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"transition": {"id": "<ID>"}}'

# 로컬 브랜치 정리
git branch -d <브랜치명>
```

---

## 완료 보고

```
PR 생성 완료
URL: https://github.com/<owner>/<repo>/pull/XXX
상태: Draft (리뷰 준비 후 gh pr ready <번호>)
```
