---
name: jira-ticket
description: md 티켓 파일을 받아 Jira 프로젝트에 이슈를 생성하고 렌더링을 검토한다. 티켓 md 파일 경로 또는 내용을 인수로 받는다.
model: sonnet
user-invocable: true
---

대상: $ARGUMENTS (md 파일 경로 또는 티켓 내용)

현재 날짜: !`date +%Y-%m-%d`

---

## 프로젝트 상수

```
PROJECT_KEY = {PROJECT_KEY}          # 예: GRT, ABC 등 실제 프로젝트 키로 교체
BASE_URL    = {ATLASSIAN_BASE_URL}   # 예: https://your-org.atlassian.net
AUTH        = ${ATLASSIAN_EMAIL}:${ATLASSIAN_API_TOKEN}
MY_ACCOUNT  = {ACCOUNT_ID}           # Jira 계정 ID
```

### 이슈 타입 ID

| 타입 | id |
|------|----|
| 작업 | 10093 |
| 하위 작업 | 10094 |
| 에픽 | 10000 |
| 스토리 | 10001 |

### 이슈 링크 타입

| 용도 | id | inward |
|------|----|--------|
| 의존 | 10000 | is blocked by |
| 연관 | 10003 | relates to |

---

## Step 1 — 티켓 파싱

md 파일 또는 내용에서 아래를 추출한다.

| md | Jira 필드 |
|----|----------|
| 제목 (`# [접두사-NN] ...`) | `summary` |
| `## 작업 내용` | `description` 본문 |
| `## 테스트 케이스` | `description` 하단 |
| `## 다이어그램` | `description` (다이어그램 설명 텍스트만, 이미지 제외) |

**Summary 접두사 → 이슈 타입 결정**

| 접두사 | issuetype id |
|--------|-------------|
| `[BE]`, `[FE]`, `[DB]`, `[INFRA]` | 10093 (작업) |
| 없음 | 10093 (작업) |

---

## Step 2 — ADF 변환 규칙

description은 반드시 **Atlassian Document Format(ADF)** 으로 작성한다. raw markdown 삽입 금지.

```json
// 헤딩
{"type":"heading","attrs":{"level":2},"content":[{"type":"text","text":"제목"}]}

// 단락
{"type":"paragraph","content":[{"type":"text","text":"본문"}]}

// 불릿 리스트
{"type":"bulletList","content":[
  {"type":"listItem","content":[
    {"type":"paragraph","content":[{"type":"text","text":"항목"}]}
  ]}
]}

// 코드 블록
{"type":"codeBlock","attrs":{"language":"sql"},"content":[{"type":"text","text":"SELECT 1;"}]}

// 굵게
{"type":"text","text":"강조","marks":[{"type":"strong"}]}
```

---

## Step 3 — 이슈 생성

**날짜 계산 (티켓 사이즈 기준)**

| 사이즈 | start → due |
|--------|-------------|
| XS | 같은 날 |
| S | D+1 |
| M | D+2 |
| L | D+3 |

**생성 순서**: 의존 없는 티켓을 먼저 생성해 `PROJ-XXXX` 키를 확보한 후, 의존 있는 티켓을 생성하고 Step 4에서 `is blocked by` 링크를 연결한다.

```bash
curl -s -X POST \
  "{ATLASSIAN_BASE_URL}/rest/api/3/issue" \
  -u "${ATLASSIAN_EMAIL}:${ATLASSIAN_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "fields": {
      "project": {"key": "{PROJECT_KEY}"},
      "issuetype": {"id": "10093"},
      "summary": "[BE] 티켓 제목",
      "description": { "type":"doc","version":1,"content": [...] },
      "assignee": {"accountId": "{ACCOUNT_ID}"},
      "customfield_10015": "YYYY-MM-DD",
      "duedate": "YYYY-MM-DD"
    }
  }' | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('key', d))"
```

생성된 `PROJ-XXXX` 키를 기록한다.

---

## Step 4 — 의존 링크 연결

의존 티켓이 있으면 각각 개별 링크로 연결한다 (범위도 건별로).

```bash
curl -s -X POST \
  "{ATLASSIAN_BASE_URL}/rest/api/3/issueLink" \
  -u "${ATLASSIAN_EMAIL}:${ATLASSIAN_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "type": {"id": "10000"},
    "inwardIssue":  {"key": "PROJ-XXXX"},
    "outwardIssue": {"key": "PROJ-YYYY"}
  }'
```

---

## Step 5 — 렌더링 검토

생성 직후 본문을 재조회해 ADF 블록 구조를 확인한다.

```bash
curl -s "{ATLASSIAN_BASE_URL}/rest/api/3/issue/PROJ-XXXX?fields=summary,description" \
  -u "${ATLASSIAN_EMAIL}:${ATLASSIAN_API_TOKEN}" \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)['fields']
print('summary:', d['summary'])
for block in (d.get('description') or {}).get('content', []):
    btype = block.get('type')
    if btype == 'paragraph':
        text = ''.join(c.get('text','') for c in block.get('content',[]))
        print('[P]', text[:80])
    elif btype == 'bulletList':
        for item in block.get('content', []):
            text = ''.join(c.get('text','') for c in item.get('content',[{}])[0].get('content',[]))
            print('[•]', text[:80])
    elif btype == 'codeBlock':
        print('[CODE]', str(block.get('content',''))[:60])
    elif btype == 'heading':
        text = ''.join(c.get('text','') for c in block.get('content',[]))
        print(f'[H{block.get(\"attrs\",{}).get(\"level\",\"?\")}]', text)
    else:
        print(f'[{btype}]')
"
```

브라우저 확인:
```bash
open "{ATLASSIAN_BASE_URL}/browse/PROJ-XXXX"
```

### 흔한 렌더링 문제

| 증상 | 원인 | 수정 |
|------|------|------|
| `##`가 그대로 출력 | raw markdown 삽입 | ADF `heading` 노드로 재작성 |
| 줄바꿈 없이 한 덩어리 | `\n` 삽입 | `paragraph` 노드로 분리 |
| 코드블록이 일반 텍스트 | ` ``` ` 그대로 삽입 | ADF `codeBlock` 노드로 재작성 |
| 불릿이 `-`로 출력 | raw markdown 삽입 | ADF `bulletList` 노드로 재작성 |

문제 발견 시 ADF로 재구성 후 PUT으로 업데이트한다.

---

## 완료 보고

```
PROJ-XXXX 생성 완료
summary: [BE] 티켓 제목
링크: {ATLASSIAN_BASE_URL}/browse/PROJ-XXXX
렌더링: ✅ (또는 이슈 내용)
```
