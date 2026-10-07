# review 모드 — 만든 화면 점검받기

산출물: 터미널 리뷰 결과 (+ 필요 시 고치기 전/후 비교 시안). **코드를 수정하지 않는다.**

## Step 1 — 대상 확정

- 검사할 코드 경로를 받는다 (예: `src/screens/Home.tsx`, `src/`).
- 같은 카테고리의 `design/tokens.json`, `design-system.md`, 관련 `*-spec.md` 가 있으면 읽는다. 판정 기준이 된다.

## Step 2 — 결정적 검사

```bash
python3 ~/.harness/skills/private-design/scripts/design_check.py source <코드 경로>
python3 ~/.harness/skills/private-design/scripts/design_check.py tokens <tokens.json>   # 있으면
```

raw 출력을 그대로 보관한다. 발견 건은 Step 4 의 p1(하드코딩 색·모드 누락) / p2(대비 미달)로 분류한다.

## Step 3 — 읽어서 판정하는 항목

변경 파일을 전부 읽는다. 추측으로 지적하지 않고 `파일:라인` 을 붙인다.

| 항목 | 기준 | 등급 |
|---|---|---|
| 상태 처리 | loading / empty / error / success 중 빠진 상태가 없다 | p1 |
| 한 모드만 구현 | 라이트·다크 중 한쪽 분기만 있다 | p1 |
| 주요 버튼 | 화면당 주요(accent) 버튼 1개. 2개 이상이면 무엇을 눌러야 할지 헷갈린다 | p2 |
| 터치 영역 | 누를 수 있는 요소의 높이 44px 이상 | p2 |
| 글자 크기 | 본문 14px 이상, 캡션 12px 이상 | p2 |
| 토큰 오용 | 역할과 다른 토큰 사용 (예: 오류 문구에 `accent`) | p3 |
| spec 불일치 | `*-spec.md` 와이어프레임·상태 문구와 다르다 | p1 |

등급과 verdict 는 [private-code-review-criteria](../../../rules/private-code-review-criteria.md) 를 따른다.

## Step 4 — 쉬운 말로 보고

등급 표기는 유지하되, 각 지적을 **사용자가 화면에서 겪는 일**로 풀어 쓴다.

```
## 디자인 리뷰
### Verdict: REQUEST_CHANGES | COMMENT | APPROVED

### p1
- src/screens/Home.tsx:42 `color: '#333'`
  → 다크 모드에서 글자가 검은 배경 위에 검게 나와 안 보여요. `text-primary` 토큰으로 바꿔야 해요.

### p2
- …

### 검사기 raw 출력
(design_check.py 출력 그대로)
```

## Step 5 — 비교 시안 (선택)

p1~p2 지적 중 말로 설명하기 어려운 것이 있으면 (예: 버튼 2개가 경쟁하는 화면), [preview](preview.md) 규칙으로 **고치기 전 / 고친 후** 2개 프레임을 그린 시안 1개를 발행한다. 지적 전부를 시안으로 만들지 않는다. 최대 3건.

## 다음 단계

수정은 이 모드의 범위가 아니다. 리뷰 결과를 입력으로 `/private-implement` 를 안내한다.
