---
name: doc-sync
description: TDD 변경 후 Confluence → 티켓 md → Jira를 순서대로 동기화한다. TDD 파일 경로 또는 변경 내용을 인수로 받는다.
model: sonnet
user-invocable: true
---

대상: $ARGUMENTS (TDD 파일 경로 또는 변경 설명)

현재 날짜: !`date +%Y-%m-%d`

---

## 동기화 순서

TDD가 기준 문서(Source of Truth)다. 아래 순서로 실행한다.

```
TDD 수정
  → Confluence용 md 재생성
    → PNG 변환 (Mermaid)
      → Confluence 페이지 업데이트
        → 티켓 md 업데이트 (영향받는 것만)
          → Jira 이슈 업데이트
```

---

## Step 1 — TDD 변경 확인

TDD 파일을 읽고 변경된 섹션을 파악한다.

- 변경 섹션: Detail Design / ERD / Sequence Diagram 등
- 영향받는 티켓 목록 파악

---

## Step 2 — Confluence용 md 재생성

TDD에서 Confluence 형식 md를 재생성한다.

Mermaid 다이어그램은 PNG로 변환 후 이미지 참조로 대체한다:

```bash
mmdc -i diagram.mmd -o diagram.png -w 4800 -b white -t default -s 4
```

부분 수정이 가능하면 전체 교체 대신 변경된 섹션만 업데이트한다.

---

## Step 3 — Confluence 페이지 업데이트

`mcp__atlassian-doodlin__update_confluence_page`를 사용한다.

주의: 전체 교체 시 Confluence에서 직접 수정한 내용이 유실된다. Confluence에서 직접 수정한 내용이 있다면 md에 먼저 반영한 후 동기화한다.

---

## Step 4 — 티켓 md 업데이트

변경된 설계가 반영된 티켓 md 파일만 업데이트한다. 변경 없는 티켓은 건드리지 않는다.

---

## Step 5 — Jira 이슈 업데이트

티켓 md가 변경된 이슈를 PUT API로 업데이트한다.

```bash
curl -s -X PUT \
  "https://doodlin.atlassian.net/rest/api/3/issue/GRT-XXXX" \
  -u "biuea@doodlin.co.kr:${ATLASSIAN_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"fields": {"description": { ...ADF... }}}'
```

---

## 완료 보고

```
동기화 완료
Confluence: <페이지 링크>
티켓 업데이트: GRT-XXXX, GRT-YYYY
Jira 반영: ✅
```
