---
description: 본격 신기능·다중 레포 변경을 받아 PRD 사전 리뷰 → TPM 분석 → prd-reviewer 검수 → TDD 강제 구현 → pr-reviewer 후처리까지 heavy 모드 개발 파이프라인을 수행합니다. 가벼운 작업은 /implement를 사용하세요.
---

# /feature — 본격 개발 파이프라인 (heavy 모드)

## 입력
`$ARGUMENTS` — PRD 문서, Jira 번호(`GRT-xxxx`), 또는 신기능 요구사항

## 언제 사용하는가
- 다중 도메인·다중 레포 변경, 3개 이상 티켓 규모
- DB 스키마 + Kafka 토픽 + BE/FE를 모두 건드리는 신기능
- TDD·다단계 리뷰가 필요한 본격 개발 사이클
- 가벼운 작업(단일 도메인, 버그 픽스)은 `/implement` 사용

---

## 파이프라인 상태 파일 — 훅 강제 연동

`.feature-pipeline-state.json` (워크스페이스 루트) 을 각 단계에서 반드시 갱신한다.
이 파일이 없거나 `step`이 `APPROVED/IMPLEMENTING`이 아니면 **훅이 구현 코드 작성을 차단한다.**

### 스키마

```json
{
  "command": "feature",
  "step": "STARTED | APPROVED | IMPLEMENTING | DONE",
  "prdPath": "...",
  "tpmAnalysisPath": "...",
  "tddPath": "...",
  "dag": { "T1": [], "T2": ["T1"], "T3": ["T1"] },
  "completed": ["T1"],
  "inFlight":  ["T2", "T3"],
  "ready":     [],
  "currentWave": 2,
  "approvedAt": "2026-05-15T10:00:00"
}
```

- `dag`: 티켓 → 선행 티켓 목록 (TPM 산출물의 의존 그래프를 파싱)
- `completed`/`inFlight`/`ready`: wave 스케줄러가 관리하는 집합
- `currentWave`: 진입한 wave 번호

### 갱신 시점

| 시점 | 실행할 명령 |
|------|------------|
| `/feature` 시작 시 | `echo '{"command":"feature","step":"STARTED","prdPath":"<입력>","approvedAt":null,"dag":{},"completed":[],"inFlight":[],"ready":[],"currentWave":0}' > .feature-pipeline-state.json` |
| Step 1-C 사용자 승인 직후 | `step:APPROVED`, `tpmAnalysisPath` 갱신, DAG 파싱하여 `dag` 필드와 초기 `ready` 셋 채움 |
| Step 1-D TDD 승인 직후 | `tddPath` 갱신 (step은 APPROVED 유지) |
| Wave 진입 (스폰 직전) | `step:IMPLEMENTING`, `inFlight ← ready`, `ready ← []`, `currentWave++` |
| Wave 완료 (모든 에이전트 종료) | `completed ← completed ∪ inFlight`, `inFlight ← []`, DAG로 새 `ready` 도출 |
| Step 5 완료 후 | `rm -f .feature-pipeline-state.json` |

---

## 파이프라인 개요

```
PRD / 요구사항
    │
    ▼
[Step 0] PRD 사전 리뷰 (prd-reviewer)
    │ PRD 자체의 명확도·모호함·누락 검수
    │ 통과 시 Step 1, 미통과 시 PM/PO 확인 요청
    ▼
[Step 1] TPM 분석 (heavy 모드)
    │ tpm-analysis.md 산출
    ▼
[Step 1-B] prd-reviewer 검수 → 피드백 루프
    │ TPM 산출물 누락·오류 검수 → 통과 시 Step 1-C
    ▼
[Step 1-C] 사용자 승인 게이트 (필수)
    │ TPM 산출물 요약 출력 → 사용자 검토·승인 대기
    │ 승인 시 Step 1-D, 수정 요청 시 Step 1 재실행
    ▼
[Step 1-D] TDD(Technical Design Document) 작성
    │ .claude/rules/tdd-template.md 따라 설계 문서 작성
    │ Background / Define Problem / Possible Solutions / Detail Design
    │ Component·Sequence·ERD 다이어그램 포함
    ▼
[Step 1-D-R] prd-reviewer TDD 검수 → 피드백 루프
    │ tdd-review-criteria 기준 누락·모순·조건부 섹션 검수 → 통과 시 사용자 승인 → Step 2
    ▼
[Step 2] 티켓 라우팅 — 레이어별 서브에이전트 배정
    │
    ├── DB 스키마 변경 → db-schema-writer (선행 필수)
    ├── Kafka 토픽 신설 → kafka-topic-provisioner (DB 이후)
    ├── BE 구현 → be-implementer (토픽/스키마 이후)
    └── FE 구현 → fe-implementer (BE 완료 이후)
    │
    ▼
[Step 3] 각 서브에이전트 — 컨텍스트 파악 → 인터페이스 설계 → TDD(RED→GREEN→detekt) → push
    │
    ▼
[Step 4] git push / gh pr create
    │  ↑ Hook 자동 강제 (settings.json):
    │  │  • push-test.sh    — 변경 모듈 테스트 통과
    │  │  • push-review.sh  — 셀프 코드 리뷰 (Must Fix → deny)
    │  │  • PR review agent — gh pr create 시 추가 리뷰
    ▼
[Step 4-B] pr-reviewer 후처리 (PR별)
    │ p0~p5 룰로 PR 전수 리뷰 → 결과 출력 → 사용자 코멘트 반영
    ▼
[Step 5] Hook/리뷰 deny → 피드백 루프 (fix → push 재시도)
```

---

## Step 0 — PRD 사전 리뷰

TPM 분석 전에 `prd-reviewer`를 호출해 **PRD 자체의 명확도**를 점검한다.

**에이전트**: `prd-reviewer`
**입력**: `$ARGUMENTS` (raw PRD/Jira 본문)
**모드**: pre-analysis (PRD 명확도 검수)

prd-reviewer는 다음을 확인한다:
- 행위자·트리거·결과가 모호하지 않은가
- 성공/실패 기준이 명시되어 있는가
- 외부 시스템 의존성·제약 조건이 누락되지 않았는가
- **be-code-convention.md 적용 여부** — PRD가 단순 "기능 추가/이전"인 경우에도 다음 항목이 작업 범위에 포함됐는지 확인. 누락 시 PRD 보강 요청.
  - Port 인터페이스 사용 → Repository/Gateway 직접 주입 전환
  - Anemic Domain Model → Rich Domain Model 재배치
  - Adapter 패턴 잔재 → DomainService로 책임 흡수
  - 임시 패키지(`dev.*` 등) → 정식 패키지 통합 시 **typealias 호환 layer 금지**

**판정**:
- 통과 → Step 1 진행
- 모호·누락 → PM/PO 확인 사항 출력 후 사용자 확인 대기

---

## Step 1 — TPM 분석 실행

`tpm` 에이전트를 호출한다.

**에이전트**: `tpm`
**모드**: `[mode: heavy]` — Phase 2 서브에이전트 prompt에 TDD 단계 포함
**입력**: `[mode: heavy] $ARGUMENTS`
**출력 저장**: `.analysis/outputs/{오늘날짜}_{기능명}/tpm-analysis.md`

TPM 산출물 항목:
- 영향 서비스 목록 (레포별)
- API 변경 목록 (신규/수정/파괴적)
- Kafka 변경 목록 (토픽/Producer/Consumer)
- 티켓 목록 (번호·제목·레포·크기·선행 관계)
- 티켓 상세 (작업 범위·완료 기준)
- **의존 그래프(DAG)** — 각 티켓의 선행/후행 카운트/병목 여부. **그룹(Group) 표기는 산출하지 않는다.** wave는 메인 오케스트레이터가 런타임에 위상정렬로 도출.

TPM 분석 완료 시 Step 1-B로 진행한다.

---

## Step 1-B — prd-reviewer 검수 (TPM 산출물 피드백 루프)

`prd-reviewer`를 다시 호출해 TPM 산출물을 검수한다.

**에이전트**: `prd-reviewer`
**입력**: `tpm-analysis.md` 경로

prd-reviewer는 다음을 확인한다:
- 요구사항 누락 (영향 서비스·API·Kafka 변경 중 빠진 항목)
- 티켓 간 의존 관계 오류
- 배포 순서 문제
- 정책 충돌·사이드 이펙트 — 코드베이스(`origin/dev`)를 직접 대조해 기존 정책과의 충돌·기존 기능 영향을 근거 코드와 함께 분석

**피드백 루프**:
- 검수 통과 → Step 1-C 진행
- 누락·오류 발견 → TPM 재분석 지시 → Step 1-B 재실행 (최대 2회)

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
- 사용자 "승인" / "OK" / "go" → Step 1-D 진행
- 사용자 수정 요청 → 수정 사항을 반영해 Step 1 재실행
- 사용자 응답 없음 → 진행하지 않음

서브에이전트를 절대 사전 호출하지 않는다.

---

## Step 1-D — TDD(Technical Design Document) 작성

TPM 산출물을 기반으로 **기술 설계 문서**를 작성한다. 구현 시작 전에 설계 의도와 변경 범위를 합의하는 단계다.

**템플릿**: `.claude/rules/tdd-template.md` 필수 준수
**출력 경로**: `.analysis/outputs/{오늘날짜}_{기능명}/tdd.md`

### 필수 섹션

| 섹션 | 내용 |
|------|------|
| Background | 프로젝트 배경·동기 |
| Overview | 무엇을·왜·어떻게의 한 줄 요약 |
| Terminology | 도메인 용어 정의 |
| Define Problem | AS-IS 구조·문제점 / TO-BE 목표 구조 |
| Possible Solutions | 벤치마킹 + 방안 비교 + 채택 사유·미채택 대안 |
| Detail Design | 클래스 역할 / Component·Sequence 다이어그램 |
| ERD | Mermaid erDiagram (요약, DDL 전문은 티켓에) |
| Testing Plan | 레벨별 테스트 전략 |
| Release Scenario | 배포 순서·마이그레이션 선후 조건·롤백 플랜 |

**선택 섹션 (조건부, [tdd-template](../rules/tdd-template.md) 기준)**: **Observability**(신규 기능·상태 전이·외부 연동 시 — 지표·알람·대시보드/로그), FE 영향 분석(API 변경 시), Security(보안 변경 시). PRD "운영: 모니터링·알림 요구사항"이 있으면 Observability로 구체화한다.

### 다이어그램 규칙

- flowchart는 항상 `LR` 방향 (TB/TD 금지)
- 노드 15개 이하, 초과 시 `subgraph` 그룹핑
- PNG 변환은 Confluence 동기화 시 (doc-sync 스킬)

### Step 1-D-R — 자동 검수 (사용자 게이트 전, 필수)

TDD 초안 작성 후 **사용자 승인 전에** `prd-reviewer`를 TDD 검수 모드로 호출한다.

**에이전트**: `prd-reviewer`
**입력**: `tdd.md` 경로 + [tdd-review-criteria](../rules/tdd-review-criteria.md)
**검수**: 필수 섹션 누락 / 조건부 섹션(Observability·롤백·FE·Security) 필요성 / 설계 정합성 / 테스트 계획 커버리지

**피드백 루프**:
- PASS → 사용자 승인 게이트 진행
- NEEDS_REVISION → TDD 보강 → Step 1-D-R 재검수 (최대 2회)

### 작성 후 사용자 승인 게이트

자동 검수(Step 1-D-R) 통과 후 **사용자에게 다음 항목 확인을 요청**한다:
- 채택한 방안이 적절한가
- AS-IS·TO-BE 비교가 정확한가
- 누락된 클래스·다이어그램·테스트 시나리오가 없는가
- 운영 관점(모니터링 지표·알람, 롤백 플랜)이 필요한 변경인데 누락되지 않았는가

**대기 액션**:
- 승인 → Step 2 진행
- 수정 요청 → 해당 섹션 수정 후 재승인 요청

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
     선행 wave의 모든 변경은 dev에 이미 머지되어 있으므로 자동 포함된다.
   - `ready`가 1개면 1개만 스폰. 9개면 9개 모두 한 메시지에 넣는다.
   - **"몇 개씩 쪼개기" 금지. 메시지를 여러 개로 나누는 것도 금지.** 동시 스폰 상한 없음.

3. **상태 파일 갱신** — 스폰 직후 `.feature-pipeline-state.json`에
   `step:IMPLEMENTING`, `inFlight ← ready`, `ready ← []`, `currentWave++`.

4. **완료 수집** — wave의 모든 에이전트 결과 수신 후 각 워크트리에서
   PR 생성·훅 통과(`push-test.sh`, `push-review.sh`, PR review agent)를 확인한다.

5. **Wave 통합 머지** — 각 워크트리의 PR을 `dev` 브랜치에 순차 머지한다.
   - 머지 순서는 임의 (같은 wave 안에서는 의존성이 없음).
   - 머지 충돌이 발생하면 **이 wave 안에서 해소**한다. 다음 wave로 미루지 않는다.
     (충돌이 자주 발생하면 분해가 잘못된 것 — `rules/ticket-guide.md`의
     "Single Writer per File" 원칙을 재검토.)
   - 머지 직후 `./gradlew build` 또는 통합 테스트 1회 실행해 회귀 없음을 확인.
   - 모든 PR 머지 완료 시 `completed ← completed ∪ inFlight`, `inFlight ← []`.

6. **새 ready 도출** — DAG에서 선행이 모두 `completed`에 들어간 티켓들을
   `ready`에 넣는다. 빈 셋이면 종료.

7. **2번으로 반복** — 다음 wave의 worktree는 **갱신된 `origin/dev` HEAD에서 분기**되므로,
   선행 wave의 변경이 자동으로 base에 포함되어 후행 PR diff에는 본인 작업만 잡힌다.

#### 강제 조항

- 한 wave 안의 모든 ready 티켓은 **반드시 하나의 어시스턴트 메시지에 병렬 스폰**한다.
  여러 메시지에 나눠 스폰하는 것은 직렬화로 간주, 금지.
- ready 셋 크기 상한 없음.
- wave 안에 병목(후행 의존 카운트 ≥ 2인 티켓)이 있어도 wave를 쪼개지 않는다.
  병목은 wave 안에서 다른 티켓과 같이 스폰되며, 후행은 자동으로 다음 wave로 밀린다 (DAG가 보장).
- **직렬 스폰은 사후 감지된다** — `custom-wave-spawn-log` hook이 스폰 타임스탬프를 기록하고 `/wave-audit`가 직렬화를 판정한다. 여러 메시지로 나눠 스폰하면 감사에 "직렬화 의심"으로 남는다.
- **typealias 호환 layer 사용 금지** — 패키지 이전 티켓이라도 호출부 import를 같은 티켓 범위에서 모두 갱신한다. "다음 wave에서 typealias 제거" 약속 패턴 금지. 한 티켓의 작업 종료 시 구 패키지 디렉토리는 완전 제거되어야 한다.
- **단순 디렉토리 이동만 하는 티켓 금지** — 패키지 이전 시 반드시 다음을 함께 수행:
  - Port 인터페이스 발견 시 제거 + Repository 직접 주입으로 전환
  - Adapter 패턴 잔재 → DomainService로 책임 흡수
  - Anemic Domain Model → Rich Domain Model 재배치
  - 호출부 import 100% 갱신 (typealias로 우회 금지)

#### 예시

```
DAG: a → {b, c, d}, b → e
Wave 1: a               (단독, 1개 tool_use)
Wave 2: b, c, d         (한 메시지에 3개 tool_use 동시)
Wave 3: e               (단독, 1개 tool_use)
```

분해 기준과 fan-out 너비 목표는 `rules/ticket-guide.md`의 "Fan-out 너비 목표" 섹션 참조.

---

## Step 3 — 서브에이전트 구현 지시 (TDD 강제)

각 서브에이전트 호출 시 아래 컨텍스트를 반드시 전달한다:

```
## 작업 티켓
{tpm-analysis.md의 해당 티켓 상세 내용 전문}

## TPM 분석 파일
{.analysis/outputs/.../tpm-analysis.md 경로}

## 구현 순서 (TDD 강제)
1. .claude/context/api/<repo>.json 로 기존 API 파악
2. .claude/context/kafka/topics.json 으로 토픽 파악
3. .claude/context/domains/<domain>.md, entities/<Entity>.md 로 도메인 지식 로드
4. .architecture/<repo>/ 스냅샷으로 코드 구조 파악
5. 구체적인 인터페이스(API 스펙, DTO, Kafka 스키마) 설계
6. 테스트 먼저 작성 (RED 확인)
7. 최소 구현 (GREEN)
8. ./gradlew detekt 통과
9. git push (훅이 자동으로 테스트 + 셀프리뷰 수행)
   - 훅이 deny하면 → 지적된 Must Fix 항목 수정 후 재시도 (최대 3회)
```

---

## Step 4 — Hook 강제 셀프리뷰 (자동, 수동 개입 불필요)

### 강제 조항 — 로컬 머지 우회 금지

Wave 종료 시 **반드시 각 브랜치를 origin에 push하고 PR을 생성**한다. 로컬 `git merge`로 우회하는 패턴은 hook 작동 기회를 박탈하므로 금지.

`git push` 또는 `gh pr create` 실행 시 `settings.json` 훅이 자동으로 개입한다.

| 훅 | 트리거 | 동작 |
|----|--------|------|
| `push-test.sh` | `git push` | 변경 모듈 Gradle 테스트 실행. 실패 → push deny |
| `push-review.sh` | `git push` | 코드 셀프리뷰. Must Fix 발견 → push deny + 이유 출력 |
| PR review agent | `gh pr create` | 전체 diff 리뷰. Must Fix → PR 생성 deny |

훅 결과 처리:
- `allow` → Step 4-B 진행
- `deny` → 지적 내용 수정 → `git push` 재시도 (최대 3회)
- 3회 초과 시 → 상위 오케스트레이터에 에스컬레이션

---

## Step 4-B — pr-reviewer 후처리 (PR별, 호출 필수)

### 강제 조항

**각 PR마다 pr-reviewer 호출은 의무**. PR 생성 직후 호출하지 않으면 머지 금지. "이미 잘 작성됐다", "단순 리네임이라 생략" 같은 우회 사유 금지. 호출 결과(REQUEST_CHANGES/APPROVED/COMMENT)를 transcript에 명시한 뒤에만 다음 단계 진행.

**에이전트**: `pr-reviewer`
**입력**: 생성된 PR 번호 또는 URL
**호출 시점**: `gh pr create` 직후 즉시. wave 종료 시점이 아닌 PR별로 즉시.

pr-reviewer는 다음을 확인한다 (be-code-convention.md 기준):
- p0 (Critical): 보안 취약점·데이터 손실·크래시 위험
- p1 (Major): harness-rules·아키텍처 레이어·UseCase Repository 직접 주입·Port 인터페이스 잔존·typealias 호환 layer 위반
- p2 (Minor): 테스트 누락·변수명 축약·메서드 100줄 초과·Anemic Entity
- p3 (Nit): 네이밍·포맷·사소한 개선
- p4 (Optional): 대안 제안

리뷰 결과는 터미널 출력만 한다. GitHub 코멘트는 사용자가 수동으로 단다.

**판정**:
- `APPROVED` → Step 5 완료 보고
- `COMMENT` → 사용자 검토 후 진행
- `REQUEST_CHANGES` → 서브에이전트 재호출하여 fix → Step 4 재진행

---

## Step 5 — 완료 보고

### 강제 조항 — harness 전수 감사

모든 wave 완료 후 반드시 `claude-framework:harness-auditor` 호출. 다음 0건 검증 필수:
- `dev.dashboard.*` 또는 임시 패키지 잔재 0건
- typealias 호환 layer 0건 (특히 `*TypeAliases.kt`, `*Compat.kt`, `*Aliases.kt` 파일)
- Port 인터페이스 잔재 0건 (`*Port.kt` 또는 `interface *Port`)
- UseCase의 Repository/Gateway/DomainEventPublisher 직접 주입 0건
- Anemic Domain Model 0건 (getter/setter만 있는 Entity)

위 5개 항목 중 1건이라도 검출되면 완료 보고 금지. fix 티켓을 추가 wave로 처리한 뒤 재감사.

### 요약 보고

모든 티켓·PR 완료 후 요약 보고:

```
## 구현 완료 — {기능명}

| 티켓 | 레포 | 브랜치 | PR | 훅 결과 | pr-reviewer | 상태 |
|------|------|--------|----|---------|-------------|------|
| T1   | ...  | ...    |... | allow   | APPROVED    | ✅   |

### 미완료 / 에스컬레이션
(있으면 기술)
```

---

## 주의사항

- PRD 사전 리뷰(Step 0) 없이 바로 TPM에 넘기지 않는다.
- 클래스명·SQL 필드·Avro 스키마를 TPM 단계에서 결정하지 않는다. 인터페이스 설계는 서브에이전트 몫이다.
- 서브에이전트가 push 훅에 의해 차단되면 fix 없이 `--no-verify`로 우회하지 않는다.
- 여러 티켓을 하나의 PR로 합치지 않는다. 티켓별 개별 브랜치·PR.
- pr-reviewer 결과는 GitHub에 자동 코멘트하지 않는다. 사용자가 수동으로 반영한다.
