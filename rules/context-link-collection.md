# 컨텍스트 링크 수집 (Context Link Collection)

PRD·Confluence·Jira·PR 본문에 걸린 링크를 빠짐없이 따라가 컨텍스트를 확보하는 공통 절차. `tpm`·`prd-reviewer`·`pr-reviewer`가 공통 참조한다.

목적: "명시된 요구사항·정책·설계 의도가 산출물/코드에 빠지거나 충돌하지 않는가"를 판단할 근거 확보.

## 절차

1. 출처 본문(PRD/Confluence/Jira/PR body)에서 **모든 링크 추출**
2. **중복 URL 제거**
3. 유형별 도구로 **병렬 조회**
4. **1-depth 재귀만** — 링크 안의 링크까지 무한히 파고들지 않는다
5. 보유 도구로만 조회 — 미보유 유형은 `WebFetch` 시도, 접근 불가 시 스킵하고 "접근 불가" 명시
6. 연결된 정책서·기획 문서의 제약·규칙도 **요구사항의 일부**로 함께 분석한다

링크가 없으면 이 단계를 건너뛴다.

## 유형별 도구

| 링크 종류 | 패턴 | 도구 |
|---|---|---|
| Jira | `atlassian.net/browse/PROJ-XXXX` | `mcp__claude_ai_Atlassian__getJiraIssue` (본문·하위 작업·AC, 여러 개면 모두) |
| Confluence | `atlassian.net/wiki/...` | `mcp__claude_ai_Atlassian__getConfluencePage` (정책서·기획서·연관 TDD) |
| Figma | `figma.com/...` | Figma MCP (`get_metadata` 구조 → `get_design_context` 컴포넌트·데이터·인터랙션) |
| GitHub PR | `github.com/.../pull/NNN` | `gh pr view <NNN> --repo <owner>/<repo> --json title,body` (제목·본문만) |
| Slack thread | `slack.com/...` | `slack_read_thread` |
| Slack channel | `app.slack.com/...` | `slack_read_channel` |
| ChannelTalk | `desk.channel.io/...` | `WebFetch` (인증 불가 시 "접근 불가" 명시) |
| 기타 (Notion 등) | — | `WebFetch` (접근 불가 시 스킵) |

> 에이전트마다 frontmatter `tools`가 다르다 (Figma는 tpm·prd-reviewer, Slack은 pr-reviewer). 보유한 도구로만 조회하고, 없는 유형은 5번 원칙대로 처리한다.
