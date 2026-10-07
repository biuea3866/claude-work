# system 모드 — 앱 전체의 색·글자·간격 규칙 만들기

산출물: `tokens.json`, `design-system.md`, `previews/design-system.html`

## Step 1 — 현황 파악

| 상황 | 할 일 |
|---|---|
| 기존 코드가 있다 | `design_check.py --json source <src 경로>` 로 하드코딩 색을 수집하고 값별 빈도를 센다. 기존 `theme/`·`tailwind.config.*`·CSS 변수 정의도 읽는다 |
| 기존 `tokens.json` 이 있다 | 읽고 "무엇을 바꾸고 싶은지"만 묻는다. 처음부터 다시 만들지 않는다 |
| 새 프로젝트다 | Step 2 인터뷰부터 한다 |

기존 코드에서 색을 수집했으면 사용자에게 쉬운 말로 요약한다. 예: "지금 화면에 서로 다른 회색이 9개, 파랑이 4개 쓰이고 있어요. 이걸 역할별로 7개로 정리할게요."

## Step 2 — 인터뷰

[interview](interview.md) 의 질문 은행에서 **느낌·참고 앱·사용 상황** 3문항만 묻는다. 화면별 질문(핵심 행동)은 spec 모드에서 한다.

## Step 3 — 팔레트 시안 비교

[preview](preview.md) 규칙으로 시안 2~3개를 발행한다. system 모드의 시안 내용은 **대표 화면 1개 + 컴포넌트 묶음**이다.

- 대표 화면: 홈 또는 목록 화면처럼 앱의 성격이 드러나는 화면
- 컴포넌트 묶음: 주요 버튼, 보조 버튼, 입력창, 카드, 목록 행, 토스트, 빈 상태
- 시안 간 차이: accent 색, 회색 위계(차갑게/따뜻하게), 모서리 둥글기, 여백 크기

## Step 4 — 확정 · 기록

사용자가 고르면 아래를 작성한다.

1. **`tokens.json`** — 고른 시안의 CSS 변수를 옮긴다. 최소 토큰: `background`, `surface`, `text-primary`, `text-secondary`, `border`, `accent`, `danger`. accent 위 글자 쌍처럼 기본 쌍 외에 검사할 조합은 `pairs` 에 추가한다 (예: `{"fg": "on-accent", "bg": "accent", "min": 4.5}`).
2. **검사** — `design_check.py tokens design/tokens.json` exit 0 을 확인한다.
3. **`design-system.md`** — 아래 섹션을 둔다.
   - 토큰 표: `tokens.json` 에서 생성한다 (토큰 · 역할 설명 · 라이트 · 다크). 역할 설명은 쉬운 말로 적는다 (예: `text-secondary` — "날짜·설명처럼 덜 중요한 글자")
   - 글자 크기 단계: 4~6단계 (예: 제목 24 / 소제목 18 / 본문 16 / 보조 14 / 캡션 12)
   - 간격 단계: 4의 배수 (4·8·12·16·24·32)
   - 모서리·그림자 규칙
   - 컴포넌트 카탈로그: 컴포넌트마다 용도 1줄, 상태(기본·누름·비활성·오류), 사용 토큰
   - 참고한 패턴: 인터뷰 결과와 참고 앱
4. **`previews/design-system.html`** — 확정 시안을 컴포넌트 카탈로그 페이지로 정리해 저장하고 같은 경로로 재발행한다.

## 코드 반영은 하지 않는다

이 모드는 규칙을 정하는 데서 끝난다. 실제 코드의 하드코딩 색을 토큰으로 바꾸는 작업은 `/private-implement` 로 안내한다. 이때 `tokens.json` 경로와 review 모드 결과를 입력으로 넘긴다.
