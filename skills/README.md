# skills — 자연어 호출 절차 (10개)

단계는 **role** 만 참조한다. 구체 agent·모델을 직접 부르지 않는다 — lint 가 `Agent(private-*)` 직접 호출을 오류로 잡는다.

## 하네스 소유 (4개)

frontmatter 에 `requires`(적합성 레벨)·`roles`(사용 role) 선언 필수.

| 스킬 | requires | 용도 |
|---|---|---|
| `/private-architect` | L1 | 개인 프로젝트 아키텍처 진단 — 앱 카테고리·진단 범위·참고 PRD를 받아 private-architect 에이전트로 AS-IS 구조 조사·트래픽 적합성 진단·구… |
| `/private-feature` | L2 | 개인 프로젝트 풀 파이프라인 — PRD 작성→검수→시니어 설계(be 먼저, fe/dba 병렬)→pm 정합 검증→구현 지휘(wave 병렬)→리뷰→PR 자동머지. 요… |
| `/private-implement` | L1 | 개인 프로젝트 경량 파이프라인 — 교차 런타임 TDD: 컨텍스트 이중 분석(A‖B) → RED(B) → GREEN/REFACTOR(A) → 결정적 게이트 → 교차 리뷰(B, 재작업 최대 2회, p0~p3 0건) → draft PR → 회고 → (사용자 확인 후) 머지… |
| `/private-release` | L1 | 개인 프로젝트 prod 릴리즈 — private-qa로 배포 가부를 조사하고, PASS면 YYYYMMDD-NN 태그를 따서 prod 프로필로 배포한다. QA FA… |

## 그 외 (6개)

외부 도구 연동 스킬. 하네스 라우팅 규약 적용 대상이 아니다.

| 스킬 |
|---|
| `/find-skills` |
| `/orca-cli` |
| `/orchestration` |
| `/orca-per-workspace-env` |
| `/computer-use` |
| `/retool-skill` |

## 커맨드 (commands/)

> `commands/*.md` 는 전부 슬래시 커맨드로 등록된다 — **이 디렉토리에 `README.md` 를 두면 `/README` 커맨드가 생긴다.** 그래서 커맨드 인덱스는 여기(스킬 README)에 둔다.

| 커맨드 | 용도 |
|---|---|
| `/private-feature-orca` | 개인 프로젝트 풀 파이프라인을 Orca orchestration으로 실행한다 — PRD→검수→시니어 설계→pm 정합→구현 wave→리뷰→PR 머지를 orca Run/Task DAG/supervise… |
| `/private-wave-audit` | 서브에이전트 스폰 ledger를 분석해 wave 병렬/직렬을 사후 감사한다. 직렬화 의심 시 근거와 함께 리포트하고 원인 점검을 안내한다. |
| `/private-ticket-wave` | 티켓 DAG를 위상정렬해 wave 단위로 병렬 구현한다 (티켓당 워크트리 1개 + 프로세스 1개). 계획 검증·사용자 확인 후 실행. 명시 호출 전용. |
