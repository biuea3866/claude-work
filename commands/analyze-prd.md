---
description: PRD·Jira·요구사항(+Figma URL·FE 레포)을 받아 디자인·FE 호출부까지 읽고 TPM 영향 분석(영향 서비스·API·Kafka·티켓 DAG)을 산출하고 prd-reviewer로 검수합니다. 구현·TDD는 하지 않으며, 분석에서 멈춰 결과를 /feature·/implement 입력으로 연결합니다.
---

# /analyze-prd — PRD 영향 분석 (구현 없음)

## 입력
`$ARGUMENTS` — PRD 문서 경로·Confluence URL, Jira 번호(`GRT-xxxx`), 또는 요구사항 텍스트
- **Figma URL** (선택) — 화면 디자인. 제공 시 MCP(claude.ai Figma)로 읽어 화면이 요구하는 데이터·상태·액션을 BE 계약 후보로 추출
- **FE 레포** (선택) — 관련 FE 레포(`greeting_front`, `greeting_career-next`, `greeting_forms-next`, `greeting_interview-next`, `greeting_trm_front` 등). 제공·식별 시 API 호출부(`@api/`, BFF)를 역추적해 기대 스키마 파악

## 언제 사용하는가
- 구현 전에 **영향 범위·티켓 분해·의존 그래프(DAG)만 먼저** 확인하고 싶을 때
- `/feature`·`/implement` 진입 전에 분석 결과를 사람이 검토·합의하고 싶을 때
- 분석에서 **멈춘다** — TDD 작성·서브에이전트 스폰·구현은 하지 않는다

## 인접 커맨드와의 차이

| 커맨드 | 범위 | 구현 |
|--------|------|------|
| `/prd` | 요구사항 → PRD 문서 작성 | ✗ |
| `/analyze-prd` | PRD → TPM 분석 + 검수 (**여기서 멈춤**) | ✗ |
| `/feature` | PRD → 분석 → TDD → 구현 → 리뷰 (heavy) | ✓ |
| `/implement` | 요구사항 → 분석 → 구현 (light) | ✓ |

`/feature`·`/implement`는 내부에서 동일한 TPM 분석을 수행한다. 본 커맨드의 산출물(`tpm-analysis.md`)이 이미 있으면 두 파이프라인의 분석 단계 입력으로 그대로 재사용할 수 있다.

---

## 파이프라인 개요

```
PRD / Jira / 요구사항
    │
    ▼
[Step 0] PRD 사전 리뷰 (prd-reviewer)
    │ PRD 자체의 명확도·모호함·누락 검수
    │ 통과 시 Step 1, 미통과 시 PM/PO 확인 요청
    ▼
[Step 1] TPM 분석 (tpm)
    │ 영향 서비스·API·Kafka 변경·티켓 목록·의존 그래프(DAG) 산출
    │ tpm-analysis.md 저장
    ▼
[Step 1-B] prd-reviewer 검수 → 피드백 루프 (최대 2회)
    │ TPM 산출물 누락·오류 검수 → 통과 시 Step 2
    ▼
[Step 2] 분석 요약 출력 + 다음 단계 안내
      구현하지 않고 종료. /feature·/implement 입력으로 연결.
```

---

## Step 0 — PRD 사전 리뷰

TPM 분석 전에 `prd-reviewer`를 호출해 **PRD 자체의 명확도**를 점검한다.

**에이전트**: `prd-reviewer`
**입력**: `$ARGUMENTS` (raw PRD/Jira 본문 — Jira 번호면 MCP로 조회한 본문)
**모드**: pre-analysis (PRD 명확도 검수)

prd-reviewer는 다음을 확인한다:
- 행위자·트리거·결과가 모호하지 않은가
- 성공/실패 기준이 명시되어 있는가
- 외부 시스템 의존성·제약 조건이 누락되지 않았는가
- **be-code-convention.md 적용 여부** — "기능 추가/이전" PRD라도 Port→직접 주입 전환, Anemic→Rich Domain 재배치, Adapter 잔재→DomainService 흡수, 임시 패키지 통합 시 typealias 호환 layer 금지가 범위에 포함됐는지 확인

**판정**:
- 통과 → Step 1 진행
- 모호·누락 → PM/PO 확인 사항을 출력하고 **사용자 확인 대기** (임의로 채우지 않는다)

---

## Step 1 — TPM 분석

`tpm` 에이전트를 호출한다.

**에이전트**: `tpm`
**입력**: `$ARGUMENTS` (+ 제공된 Figma URL·FE 레포)
**출력 저장**: `.analysis/outputs/{YYYYMMDD}_{기능명}/tpm-analysis.md`
  - Jira 입력이면 `{YYYYMMDD}_{GRT-번호}` 사용 (예: `20260527_GRT-4324`)

> Figma URL·FE 레포가 제공되면 tpm이 Phase 1(2-A·2-B)에서 디자인(MCP)·FE 호출부를 읽어 BE 계약을 역산한다. 화면·FE가 요구하는 데이터·액션이 API 변경 목록에 반영된다.

TPM 산출물 항목:
- 영향 서비스 목록 (레포별)
- API 변경 목록 (신규/수정/파괴적/삭제 + 영향 Consumer)
- Kafka 변경 목록 (토픽/Producer/Consumer/Avro 신규 여부)
- 티켓 목록 (번호·제목·레포·담당·크기·선행 관계)
- 티켓 상세 (배경·작업 범위·완료 기준)
- **의존 그래프(DAG)** — 각 티켓의 선행/후행 카운트/병목 여부. **그룹(Group) 표기는 산출하지 않는다.** wave는 다운스트림 파이프라인이 런타임에 위상정렬로 도출.
- 초기 ready 셋 (선행 없는 티켓)

TPM 분석 완료 시 Step 1-B로 진행한다.

---

## Step 1-B — prd-reviewer 검수 (피드백 루프)

`prd-reviewer`를 다시 호출해 TPM 산출물을 검수한다.

**에이전트**: `prd-reviewer`
**입력**: `tpm-analysis.md` 경로

prd-reviewer는 다음을 확인한다:
- 요구사항 누락 (영향 서비스·API·Kafka 변경 중 빠진 항목)
- 티켓 간 의존 관계 오류·순환 의존
- 배포 순서 문제 (DB 선행, Kafka 토픽 선행, FE 후행)
- **정책 충돌·사이드 이펙트** — 코드베이스(`origin/dev`)를 직접 대조해 기존 정책과의 충돌·기존 기능에 미칠 영향을 근거 코드와 함께 분석

**피드백 루프**:
- 검수 통과(PASS) → Step 2 진행
- NEEDS_REVISION/BLOCKED → 지적 사항을 반영해 TPM 재분석 지시 → Step 1-B 재실행 (**최대 2회**)
- 2회 후에도 미통과 → 잔여 이슈를 그대로 Step 2 요약에 명시하고 사용자 판단에 맡긴다

---

## Step 2 — 분석 요약 출력 (구현하지 않고 종료)

검수 통과 후 다음 요약을 출력하고 **종료**한다. 서브에이전트를 스폰하지 않는다.

```
## PRD 분석 완료 — {기능명}

영향 서비스: {레포 수}개 — {레포 목록}
API 변경: 신규 {N} / 수정 {N} / 파괴적 {N}
Kafka 변경: 토픽 {N} / Producer {N} / Consumer {N}
티켓: 총 {N}개 (S {n} / M {n} / L {n})
초기 ready 셋 (Wave 1 후보): {선행 없는 티켓}
의존 그래프: DAG {N}행 (병목 {n} / 단독 {n})
prd-reviewer 판정: PASS / NEEDS_REVISION (잔여 이슈 {n}건)

전체 산출물: {tpm-analysis.md 경로}

다음 단계:
- 본격 신기능 (다중 레포):  /feature {tpm-analysis.md 또는 PRD 경로}
- 단일 도메인 변경:         /implement {동일 경로}
- Jira 티켓 등록:           /jira-ticket {티켓 md 경로}
```

---

## 주의사항

- **구현·TDD 작성·서브에이전트 스폰 금지.** 분석 산출과 검수에서 멈춘다.
- `.feature-pipeline-state.json`의 구현 게이트를 `IMPLEMENTING`으로 바꾸지 않는다. 본 커맨드는 구현 훅을 통과시키지 않는다.
- 클래스명·메서드 시그니처·SQL 필드·Avro 스키마 필드를 결정하지 않는다 — 인터페이스 설계는 구현 단계(서브에이전트) 몫이다.
- 미결 사항은 임의로 결정하지 않고 요약의 "잔여 이슈"로 남긴다.
