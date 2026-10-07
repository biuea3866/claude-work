---
name: private-design
description: 개인 프로젝트 디자인 — 디자인을 모르는 사용자를 전제로, 쉬운 질문 → HTML 시안 2~3개 비교 → 선택으로 디자인을 정한다. 모드 3개 — system(코드·취향에서 색·글자·간격 토큰과 컴포넌트 카탈로그 구축), spec(화면 와이어프레임·상태 표 설계), review(화면의 색 하드코딩·다크 모드 누락·대비·상태 처리 검수). "디자인 시스템", "화면 디자인", "UI 시안", "디자인 토큰", "다크 모드 점검", "디자인 리뷰" 요청 시 사용. 코드 버그·아키텍처 리뷰는 /private-implement 의 review.code 담당.
user-invocable: true
requires: L2
roles: [design.fe]
---

요청 (모드 system|spec|review + 대상): $ARGUMENTS

현재 디렉토리: !`pwd`
프로젝트 카테고리 목록: !`ls -1 /Users/biuea/Desktop/dpdpdndn/프로젝트/ 2>/dev/null || echo "(디렉토리 없음)"`

라우팅 (roles.json active_profile 해석):
!`~/.harness/bin/harness role --compact design.fe`

---

## 실행 규약

단계는 **role** 로만 지정한다. 구체 agent·모델·런타임은 `roles.json` 이 정한다 — 스킬에 하드코딩하지 않는다.

- 위 라우팅 표의 `invoke` 를 **그대로** 실행한다. `claude/*` 는 `Agent(...)`, `codex/*` 는 Bash 로 `codex exec`(페르소나를 stdin 으로 주입).
- `codex exec` 는 별도 세션이라 컨텍스트를 물려받지 않는다 — **입력·산출 경로와 계약을 프롬프트에 전부 적고**, 산출물은 파일로 받는다.
- 인터뷰·시안 비교는 사용자와 주고받아야 하므로 **메인 세션이 소유**한다. 서브에이전트는 사용자에게 질문할 수 없다.

## 전제 — 사용자는 디자인 용어를 모른다

이 스킬의 핵심 규약이다. 모든 단계에 적용한다.

1. **명세를 요구하지 않는다.** "색은 뭘로 할까요?"처럼 묻지 않는다. 생활 언어로 묻고([interview](references/interview.md)), 답을 디자인 결정으로 번역하는 것은 스킬의 몫이다.
2. **글이 아니라 화면으로 보여 준다.** 결정이 필요하면 HTML 시안 2~3개를 렌더링해 고르게 한다([preview](references/preview.md)). 토큰 표만 보여 주고 판단을 요구하지 않는다.
3. **피드백은 평소 말로 받는다.** "답답해", "너무 튀어", "2번 배치에 3번 색" 같은 말을 받아 수정한다. 디자인 용어로 되묻지 않는다.
4. **디자인 용어를 쓸 때는 풀어 쓴다.** 예: "대비(글자와 배경의 밝기 차이)", "accent(화면에서 가장 눈에 띄게 할 색 1가지)".
5. **답이 없으면 기본값으로 간다.** 기본값은 토스 패턴이다([private-fe-convention](../../rules/private-fe-convention.md) "디자인 기준"). "알아서 해 줘"도 유효한 답이다.

## Step 0 — 모드·카테고리 판정

- 첫 인수가 `system` / `spec` / `review` 이면 그 모드로 간다.
- 인수가 없거나 자연어뿐이면 의도로 판정한다. 판정이 갈리면 AskUserQuestion 으로 묻는다. 선택지는 쉬운 말로 적는다: "앱 전체의 색·글자 규칙 정하기(system)" / "화면 하나 설계하기(spec)" / "만든 화면 점검받기(review)".
- 앱 카테고리를 확정한다. 위 목록에서 고르게 하고, 새 카테고리를 임의로 만들지 않는다.

## 산출물 위치 (공통)

`/Users/biuea/Desktop/dpdpdndn/프로젝트/{앱 카테고리}/design/`

| 파일 | 내용 | 만드는 모드 |
|---|---|---|
| `tokens.json` | 시맨틱 토큰의 라이트/다크 값. **값의 원본(SSOT)** | system |
| `design-system.md` | 토큰 표·글자 크기 단계·간격·컴포넌트 카탈로그. 토큰 표는 `tokens.json` 에서 생성하고 손으로 고치지 않는다 | system |
| `{YYYYMMDD}-{화면명}-spec.md` | 화면 설계 (와이어프레임·상태 표·사용 토큰) | spec |
| `previews/*.html` | 사용자가 고른 시안의 최종본 | system, spec |

`tokens.json` 형식과 검사기는 [design_check.py](scripts/design_check.py) 를 따른다.

## 모드별 절차

선택된 모드의 문서 **하나만** 읽고 따른다. 셋 다 읽지 않는다.

| 모드 | 절차 | 선행 조건 |
|---|---|---|
| `system` | [references/system.md](references/system.md) | 없음 |
| `spec` | [references/spec.md](references/spec.md) | `tokens.json` (없으면 system 을 먼저 안내) |
| `review` | [references/review.md](references/review.md) | 검사할 코드 경로 |

## 결정적 검사 (계산으로 판정)

대비·모드 누락·색 하드코딩은 LLM 판단이 아니라 검사기로 판정한다.

```bash
python3 ~/.harness/skills/private-design/scripts/design_check.py tokens <tokens.json>
python3 ~/.harness/skills/private-design/scripts/design_check.py source <코드 또는 시안 경로...>
```

exit 0 = 발견 없음, 1 = 발견 있음, 2 = 사용법 오류. 시안 HTML 도 사용자에게 보여 주기 전에 두 검사를 통과해야 한다.

## 완료 보고

> 완료 단언은 `rules/COMPLETION-RULE.md` 의 §1~4 를 모두 충족해야 한다.

```
## /private-design {모드} 결과
- 산출물: {파일 경로 목록}
- 시안 링크: {Artifact URL — 없으면 "없음"}
- 검사기: tokens exit {n} / source exit {n} (raw 출력 첨부)
- 사용자가 고른 것: {쉬운 말 1~2줄}
- 다음 단계: {예: "spec 으로 첫 화면 설계" / "review 지적 3건 수정은 /private-implement"}
```
