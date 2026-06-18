---
name: review
description: 현재 브랜치 또는 PR의 코드를 harness-rules·아키텍처·테스트·보안 관점으로 검수한다. PR 번호, 브랜치명, 또는 인수 없이 현재 브랜치 diff를 받는다.
model: opus
user-invocable: true
---

리뷰 대상: $ARGUMENTS  (PR 번호 / 브랜치명 / 비어있으면 현재 브랜치)

현재 브랜치: !`git branch --show-current 2>/dev/null || echo "(git 없음)"`
원격 최신: !`git fetch origin --quiet 2>/dev/null && echo "fetch OK" || echo "fetch 실패"`

---

**diff 확인 순서**

| 입력 | 명령 |
|------|------|
| PR 번호 `123` | `gh pr view 123 --json files,title,body && gh pr diff 123` |
| 브랜치명 | `git diff origin/dev...<브랜치> --stat` → 파일별 Read |
| 비어있음 | `git diff origin/dev...HEAD --name-only` → 파일별 Read |

**반드시 `code-reviewer` 에이전트를 호출해 검수를 위임한다.**

```
Agent(subagent_type="code-reviewer", prompt="
  <diff 또는 PR 번호>를 리뷰해줘.
  레포: <레포명>
  브랜치: <브랜치명>
  harness-rules 위반 + 아키텍처 레이어 + 테스트 누락 + 보안 전수 검토.
  PR이 있으면 gh pr review <번호>로 verdict 남기고, 없으면 터미널 출력.
")
```

리뷰어 에이전트가 반환한 결과를 그대로 사용자에게 전달한다.
