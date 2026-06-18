# 문서 동기화 가이드

## 원칙

TDD(Technical Design Document)가 기준 문서(Source of Truth)입니다. TDD가 변경되면 Confluence → 티켓 md → Jira 순서로 동기화합니다.

→ 실행은 `doc-sync` 스킬을 사용합니다.

## 주의사항

- **전체 교체 시 Confluence 수동 편집 내용이 유실됩니다.** Confluence에서 직접 수정한 내용이 있다면 md에 먼저 반영한 후 동기화합니다.
- 부분 수정이 가능하면 전체 교체 대신 해당 섹션만 업데이트합니다.
