---
id: private-prd-template
title: [개인] PRD 템플릿
scope: task
level: MUST
context: private
---

# [개인] PRD 템플릿

PRD(Product Requirements Document) 구조. `private-prd-writer`가 작성 기준으로, `private-prd-reviewer`가 검수 기준으로, `private-senior-pm`이 정합 검증의 원본으로 참조한다 (SSOT).

구조·문체는 사내 PO PRD(예: Greeting Product 「PRD : 자동화 1차 - 알림 고도화」)를 기준으로 한다 — 개조식·표 중심, 페르소나별 문제 → 해결, 기능별 User Story + Acceptance Criteria, As-Is / To-Be 변경점.

## 저장 규칙

- 개인 프로젝트 경로: `/Users/biuea/Desktop/dpdpdndn/프로젝트/{앱 카테고리}/`
- 파일명: `{YYYYMMDD}-{기능명}-prd.md`
- 앱 카테고리가 특정되지 않으면 디렉토리 목록을 확인시키고 사용자가 지정 — 임의로 새 카테고리를 만들지 않는다.
- **회사 프로젝트는 개인 경로에 저장하지 않는다** — 작업 파일은 세션 임시 디렉토리, 게시처는 사용자가 지정한 위치(예: Confluence 폴더·비공개 페이지). 게시 전 사용자 승인.

## 필수 구조

```markdown
# PRD : {기능명}

| version | date | change history |
| --- | --- | --- |
| v0.1 | YYYY-MM-DD | 초안 작성 |

# Overview

| Epic / 과제 ID | {티켓 키 또는 과제 ID} |
| --- | --- |
| Product Lead | {역할 또는 @mention} |
| Tech Lead | {역할 또는 @mention} |
| Product Designer | {역할 또는 @mention — 없으면 "없음"} |
| Target release | {로드맵 단계(분기) — 날짜는 설계 이후 확정. 미정이면 TBU} |
| 근거 문서 | {1-pager·로드맵·회의록 링크} |
| Design guide | {Figma 링크 — 없으면 "없음"} |

| 구분 | Checklist |
| --- | --- |
| 플랜 | - [ ] 기능별 플랜 정의 - [ ] 다운그레이드·Lock 시 정책 |
| 권한 | - [ ] 기능에서 쓰는 권한 정의 |
| 로그 | - [ ] 활동기록·설정 히스토리 정의 |
| Open API | - [ ] 제공 중인 API 영향도 |
| 번역 | - [ ] 영문 대응 여부 |
| 모바일 | - [ ] 모바일 제공 범위 |
| 백오피스 | - [ ] 운영 확인 UI 필요 여부 |
| 보안 검토 | - [ ] 개인정보 활용·추가 수집 여부 |

# 요구사항

### 사용자 문제 → 해결 방안 정의

| 페르소나 | 사용자 문제 (As-Is) | 해결 방안 |
| --- | --- | --- |
| {구직자 / 채용담당자 / 평가자 …} | {현재 불편 → 결과로 생기는 문제} | NEW / UPDATE **[기능명]** _ {한 줄 설명} |

### 범위
- In = {이번 PRD에서 하는 것}
- Out = {하지 않는 것 + 사유} — 오버엔지니어링 차단

### 기대 효과
1. {지표} = {현재값} → {목표값} (측정 방법·분모)

### 인사이트
- {VOC·데이터·경쟁사에서 확인한 사실 1줄씩}

| 제품 | 참조 패턴 | 우리와 차이 | URL |
| --- | --- | --- | --- |
{실제 제품 2개 이상}

# 세부 정책

## 1. [{기능명}] 기능 추가 _ ({하위 항목})
- 우선순위 = P0 | P1 | P2
- Plan별 제한 = {없음 | 플랜명}

### User Story + Acceptance Criteria
1. **{사용자}는 {무엇}을 할 수 있어야 한다.**
    1. {조건·제약 — "~해야 한다" / "~할 수 없어야 한다"}

### 주요 작업 포인트 (변경점)

| | As-Is | To-Be |
| --- | --- | --- |
| 작업 위치 | {DELETE 기존 위치} | NEW {신규 위치} |

### 상세 정책
- 조건 = {발생·노출 조건}
- 제외 조건 = {발생하지 않는 경우}
- **{예외 케이스 굵게 한 줄}**
    - {처리 방식}

### 예상 작업 위치

| 위치 | 필수 구현 항목 |
| --- | --- |

## 2. …

# 비기능·운영
- 성능 = {수치 — P95 500ms 등}
- 모니터링 = {배포 후 볼 지표·알림}

# Backoffice
# 번역
# 설정 히스토리
# Open Questions
| # | 질문 | 결정 | 반영 버전 |

# 참고 자료
```

## 작성 규칙

- **문체 = 개조식 명사형** ([output-style](./output-style.md) "문서 문체") — "~필요", "~불가", "~로 변경". 서술형 "~합니다" 금지.
- **압축 기호** — `=`(값·정의), `→`(전환·결과), As-Is / To-Be 표. 변경 성격 태그 `NEW` / `UPDATE` / `DELETE` / `KEEP`, 우선순위 태그 `P1`·`P2`(P0은 기본값이라 생략 가능).
- **"무엇을"까지만** — "어떻게"(클래스·스키마·기술 선택)는 TDD(Technical Design Document) 영역.
- **가정 금지** — 해석이 갈리는 지점은 작성 전 질문 목록으로 확인. 사소한 디테일만 초안 + Open Questions.
- **추상 표현 금지, 수치로** — "빠른 응답" ✗ → "P95 500ms 이내" ✓.
- **예외는 정책 안에** — 각 기능의 상세 정책에 제외 조건·예외 케이스 필수(실패·빈 상태·권한 없음·중복).
- **내부 근거 ID는 본문에 섞지 않는다** — 섹션 끝 `근거:` 한 줄로 모은다. 분석 점수(RICE 등)는 PRD에 넣지 않는다.
- 해당 없는 섹션·체크리스트 항목 = "해당 없음 + 사유" 1줄 (placeholder 금지).
- 기존 PRD와 모순 금지 — 같은 제품의 기존 PRD를 먼저 읽는다.
- 결정이 바뀌면 version 표에 한 줄 추가 (근거 쓰레드·회의록 링크).

## 검수 연계 (private-prd-reviewer)

- 필수 섹션(version 표·Overview·Checklist·사용자 문제 → 해결 방안·범위·기대 효과·세부 정책·Open Questions) 누락·placeholder → NEEDS_REVISION
- 기능별 우선순위 미부여, User Story + AC 없음 → NEEDS_REVISION
- 기대 효과가 측정 불가(현재값·목표값·측정 방법 없음) → NEEDS_REVISION
- 상세 정책에 제외 조건·예외 케이스 부재 → NEEDS_REVISION
- 서술형 문체·본문 내 내부 ID 나열 → p3 수준 지적(문체 수정 요청)
- 코드베이스 충돌(기존 기능·정책과 모순, As-Is 사실 오류)은 reviewer가 코드를 읽어 확인

## 참고 문서

- [private-tdd](./private-tdd.md) — PRD 승인 후 설계 문서
- [output-style](./output-style.md) — 문서 문체·수치 구체성
