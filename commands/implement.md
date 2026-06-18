---
description: 가벼운 요구사항(텍스트/Jira 번호/URL)을 받아 TPM 분석 → TDD 구현 → Hook 강제 셀프리뷰까지 light 모드 개발 파이프라인을 수행합니다. PRD 사전 리뷰·pr-reviewer 후처리가 필요한 본격 개발은 /feature를 사용하세요.
---

# /implement — 개발 파이프라인 (light 모드)

## 입력
`$ARGUMENTS` — 가벼운 요구사항 텍스트, Jira 번호(`GRT-xxxx`), 또는 간단한 기능 설명

## 언제 사용하는가
- 단일 도메인 변경, 1~2개 티켓 규모의 가벼운 작업
- 단순 기능 추가·버그 픽스 (TDD는 동일하게 적용, 단 PRD 사전 리뷰·pr-reviewer 후처리는 생략)
- 본격 신기능·다중 레포 변경은 `/feature` 사용

---

## 파이프라인 개요

```
PM 요구사항
    │
    ▼
[Step 1] TPM 분석
    │ tpm-analysis.md 산출
    ▼
[Step 1-B] prd-reviewer 검수 → 피드백 루프
    │ 누락·오류 발견 시 TPM 재분석 → 통과 시 Step 1-C
    ▼
[Step 1-C] 사용자 승인 게이트 (필수)
    │ TPM 산출물 요약 출력 → 사용자 검토·승인 대기
    │ 승인 시 Step 2, 수정 요청 시 Step 1 재실행
    ▼
[Step 2] 티켓 라우팅 — 레이어별 서브에이전트 배정
    │
    ├── DB 스키마 변경 → db-schema-writer (선행 필수)
    ├── Kafka 토픽 신설 → kafka-topic-provisioner (DB 이후)
    ├── BE 구현 → be-implementer (토픽/스키마 이후)
    └── FE 구현 → fe-implementer (BE 완료 이후)
    │
    ▼
[Step 3] 각 서브에이전트 — 컨텍스트 파악 → 인터페이스 설계 → TDD(RED→GREEN→detekt)
    │
    ▼
[Step 4] git push / gh pr create
    │  ↑ Hook 자동 강제 (settings.json):
    │  │  • push-test.sh    — 변경 모듈 테스트 통과
    │  │  • push-review.sh  — 셀프 코드 리뷰 (Must Fix → deny)
    │  │  • PR review agent — gh pr create 시 추가 리뷰
    ▼
[Step 5] Hook deny → 피드백 루프 (fix → push 재시도)
```

---

## Step 1 — TPM 분석 실행

아래 `tpm` 에이전트를 호출한다.

**에이전트**: `tpm`
**모드**: `[mode: light]` — Phase 2 서브에이전트 prompt에서 TDD 단계 제외
**입력**: `[mode: light] $ARGUMENTS`
**출력 저장**: `.analysis/outputs/{오늘날짜}_{기능명}/tpm-analysis.md`

TPM 에이전트가 다음을 산출한다:
- 영향 서비스 목록 (레포별)
- API 변경 목록 (신규/수정/파괴적)
- Kafka 변경 목록 (토픽/Producer/Consumer)
- 티켓 목록 (번호·제목·레포·크기·선행 관계)
- 티켓 상세 (작업 범위·완료 기준)
- **의존 그래프(DAG)** — 각 티켓의 선행/후행 카운트/병목 여부. **그룹(Group) 표기는 산출하지 않는다.** wave는 메인 오케스트레이터가 런타임에 위상정렬로 도출.

TPM 분석이 완료되면 결과를 파일에 저장하고 Step 1-B로 진행한다.

---

## Step 1-B — prd-reviewer 검수 (피드백 루프)

`prd-reviewer` 에이전트를 호출해 TPM 산출물을 검수한다.

**에이전트**: `prd-reviewer`  
**입력**: `tpm-analysis.md` 경로

prd-reviewer는 다음을 확인한다:
- 요구사항 누락 (영향 서비스·API·Kafka 변경 중 빠진 항목)
- 티켓 간 의존 관계 오류
- 배포 순서 문제

**피드백 루프**:
- 검수 통과 → Step 1-C 진행
- 누락·오류 발견 → TPM 에이전트에 재분석 지시 → Step 1-B 재실행 (최대 2회)

---

## Step 1-C — 사용자 승인 게이트 (필수)

prd-reviewer 통과 후 **반드시 사용자에게 TPM 산출물 요약을 보여주고 승인을 받는다**.

요약 출력 형식:
```
## TPM 분석 요약 — {기능명}

영향 서비스: {레포 수}개 — {레포 목록}
API 변경: 신규 {N}개 / 수정 {N}개 / 파괴적 {N}개
Kafka 변경: 토픽 {N}개 / Producer {N} / Consumer {N}
티켓: 총 {N}개 (S {n} / M {n} / L {n})
초기 ready 셋 (Wave 1 동시 진입 후보): {선행 없는 티켓 목록}
의존 그래프: DAG 표 N행 (병목 {n}건, 단독 {n}건)

전체 산출물: {tpm-analysis.md 경로}
```

**대기 액션**:
- 사용자 "승인" / "OK" / "go" → Step 2 진행
- 사용자 수정 요청 → 수정 사항을 반영해 Step 1 재실행
- 사용자 응답 없음 → 진행하지 않음

서브에이전트를 절대 사전 호출하지 않는다.

---

## Step 2 — 티켓 라우팅

TPM 산출물의 **의존 그래프(DAG)**를 wave 스케줄러로 처리하여 서브에이전트에 배정한다.

### 라우팅 규칙

| 티켓 레포 / 성격 | 서브에이전트 |
|-----------------|-------------|
| `greeting-db-schema` / SQL 마이그레이션 | `db-schema-writer` |
| `greeting-topic` / Kafka 토픽 신설 | `kafka-topic-provisioner` |
| FE 레포 (`greeting_front`, `greeting_career-next`, `greeting_forms-next`, `greeting_interview-next`, `greeting_trm_front`) | `fe-implementer` |
| 그 외 모든 Kotlin BE 레포 | `be-implementer` |

### 배포 순서 강제
- DB 스키마 티켓 → 완료 확인 후 다음 그룹 진행
- Kafka 토픽 티켓 → DB 이후, BE 이전
- FE는 BE API 완료 후 착수

### 실행 모델 — Wave 스케줄러 (claude-code 메인이 수행, fan-out 강제)

오케스트레이터는 **claude-code 메인 세션**이다. TPM 에이전트는 분석만 하고 서브에이전트를 호출하지 않는다.

#### 알고리즘 (메인 세션이 매 wave마다 수행)

1. **DAG 로드** — `tpm-analysis.md`의 "의존 그래프(DAG)" 섹션을 파싱.
   초기 상태: `inFlight = ∅`, `completed = ∅`, `ready = {선행 없는 모든 티켓}`.

2. **Wave 진입** — `ready`의 모든 티켓을 **하나의 어시스턴트 메시지**에
   Agent 도구 tool_use를 N개 묶어 동시 스폰한다.
   - 각 에이전트는 `isolation: "worktree"` 모드로 호출하며,
     **현재 시점의 `origin/dev` HEAD에서 자기 브랜치(`feat/<티켓번호>`)를 분기**한다.
   - `ready`가 1개면 1개만 스폰. 9개면 9개 모두 한 메시지에 넣는다.
   - **"몇 개씩 쪼개기" 금지. 메시지를 여러 개로 나누는 것도 금지.** 동시 스폰 상한 없음.

3. **완료 수집** — wave의 모든 에이전트 결과 수신 후 각 워크트리에서
   PR 생성·훅 통과를 확인한다.

4. **Wave 통합 머지** — 각 워크트리의 PR을 `dev` 브랜치에 순차 머지한다.
   - 머지 충돌 발생 시 이 wave 안에서 해소 (다음 wave로 미루지 않음).
   - 모든 PR 머지 완료 시 `completed ← completed ∪ inFlight`, `inFlight ← []`.

5. **새 ready 도출** — DAG에서 선행이 모두 `completed`에 들어간 티켓들을
   `ready`에 넣는다. 빈 셋이면 종료.

6. **2번으로 반복** — 다음 wave의 worktree는 **갱신된 `origin/dev` HEAD에서 분기**되므로,
   선행 wave의 변경이 자동으로 base에 포함되어 후행 PR diff에는 본인 작업만 잡힌다.

#### 강제 조항

- 한 wave 안의 모든 ready 티켓은 **반드시 하나의 어시스턴트 메시지에 병렬 스폰**한다.
  여러 메시지에 나눠 스폰하는 것은 직렬화로 간주, 금지.
- ready 셋 크기 상한 없음.
- wave 안에 병목(후행 의존 카운트 ≥ 2인 티켓)이 있어도 wave를 쪼개지 않는다.
  병목은 wave 안에서 다른 티켓과 같이 스폰되며, 후행은 자동으로 다음 wave로 밀린다 (DAG가 보장).
- **직렬 스폰은 사후 감지된다** — `custom-wave-spawn-log` hook이 스폰 타임스탬프를 기록하고 `/wave-audit`가 직렬화를 판정한다. 여러 메시지로 나눠 스폰하면 감사에 "직렬화 의심"으로 남는다.

#### 예시

```
DAG: a → {b, c, d}, b → e
Wave 1: a               (단독, 1개 tool_use)
Wave 2: b, c, d         (한 메시지에 3개 tool_use 동시)
Wave 3: e               (단독, 1개 tool_use)
```

분해 기준과 fan-out 너비 목표는 `rules/ticket-guide.md`의 "Fan-out 너비 목표" 섹션 참조.

---

## Step 3 — 서브에이전트 구현 지시

각 서브에이전트 호출 시 아래 컨텍스트를 반드시 전달한다:

```
## 작업 티켓
{tpm-analysis.md의 해당 티켓 상세 내용 전문}

## TPM 분석 파일
{.analysis/outputs/.../tpm-analysis.md 경로}

## 구현 순서 (TDD: Test-Driven Development)
1. .claude/context/api/<repo>.json 로 기존 API 파악
2. .claude/context/kafka/topics.json 으로 토픽 파악
3. .claude/context/domains/<domain>.md, entities/<Entity>.md 로 도메인 지식 로드
4. .architecture/<repo>/ 스냅샷으로 코드 구조 파악
5. 구체적인 인터페이스(API 스펙, DTO, Kafka 스키마) 설계
6. 테스트 먼저 작성 (RED 확인)
7. 최소 구현 (GREEN)
8. ./gradlew detekt 통과
9. git push (훅이 자동으로 테스트 + 셀프리뷰 수행)
   - 훅이 deny하면 → 지적된 Must Fix 항목 수정 후 재시도
```

---

## Step 4 — Hook 강제 셀프리뷰 (자동, 수동 개입 불필요)

`git push` 또는 `gh pr create` 실행 시 `settings.json` 훅이 자동으로 개입한다.

| 훅 | 트리거 | 동작 |
|----|--------|------|
| `push-test.sh` | `git push` | 변경 모듈 Gradle 테스트 실행. 실패 → push deny |
| `push-review.sh` | `git push` | 코드 셀프리뷰. Must Fix 발견 → push deny + 이유 출력 |
| PR review agent | `gh pr create` | 전체 diff 리뷰. Must Fix → PR 생성 deny |

**서브에이전트는 훅 결과를 확인하고:**
- `allow` → 완료 보고
- `deny` → 지적 내용 수정 → `git push` 재시도 (최대 3회)
- 3회 초과 시 → 상위 오케스트레이터에 에스컬레이션

---

## Step 5 — 완료 보고

모든 티켓 서브에이전트 완료 후 요약 보고:

```
## 구현 완료 — {기능명}

| 티켓 | 레포 | 브랜치 | PR/커밋 | 상태 |
|------|------|--------|---------|------|
| T1   | ...  | ...    | ...     | ✅   |

### 미완료 / 에스컬레이션
(있으면 기술)
```

---

## 주의사항

- TPM 분석 없이 바로 구현하지 않는다. 반드시 Step 1을 먼저 완료한다.
- 클래스명·SQL 필드·Avro 스키마를 TPM 단계에서 결정하지 않는다. 인터페이스 설계는 서브에이전트 몫이다.
- 서브에이전트가 push 훅에 의해 차단되면 fix 없이 `--no-verify`로 우회하지 않는다.
- 여러 티켓을 하나의 PR로 합치지 않는다. 티켓별 개별 브랜치·PR.
