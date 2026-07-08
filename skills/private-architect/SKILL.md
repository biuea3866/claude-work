---
name: private-architect
description: 개인 프로젝트 아키텍처 진단 — 앱 카테고리·진단 범위·참고 PRD를 받아 private-architect 에이전트로 AS-IS 구조 조사·트래픽 적합성 진단·구조적 해결책 후보 비교·바운디드 컨텍스트 판단·장기 도메인 진화 계획을 산출한다. 기능 단위 설계·구현은 /private-feature.
user-invocable: true
---

진단 대상 (앱 카테고리 / 진단 범위 / 참고 PRD 경로): $ARGUMENTS

현재 디렉토리: !`pwd`
개인 프로젝트 마커: !`[ -f "$(git rev-parse --show-toplevel 2>/dev/null)/.claude/private-project" ] && echo "OK" || echo "없음 — 개인 프로젝트가 아니면 이 스킬을 쓰지 않는다"`
프로젝트 카테고리 목록: !`ls -1 /Users/biuea/Desktop/dpdpdndn/프로젝트/ 2>/dev/null || echo "(디렉토리 없음)"`

---

개인 프로젝트 전용 아키텍처 진단 진입점. **시스템 전체·장기 관점** 판단이 필요할 때 사용한다 — 기능 단위 TDD·티켓 분해·구현은 `/private-feature`(또는 `private-senior-be`) 담당이다.

## Step 1 — 범위·카테고리 확정

1. 마커가 없으면 중단하고 안내한다.
2. 앱 카테고리가 인수에 없으면 위 카테고리 목록을 보여주고 사용자가 지정하게 한다 — 임의로 새 카테고리를 만들지 않는다.
3. 진단 범위(전체 아키텍처 / 특정 병목 / 도메인 경계 / 장기 진화 계획 등)와 참고 PRD 경로를 파악한다. 해석이 갈리면 스폰 전에 질문한다 (가정 금지).

## Step 2 — 아키텍트 스폰

- `Agent(private-architect)` — 인수(앱 카테고리 / 진단 범위 / 참고 PRD 경로)를 그대로 전달한다.
- 에이전트가 AS-IS 조사 → 트래픽 진단 → 경쟁사 비교 → 해결책 후보 → 바운디드 컨텍스트 판단 → 장기 진화 계획을 수행하고 아키텍처 문서를 저장한다.
- 이 스킬은 단일 에이전트 진입점이므로 병렬 스폰이 없다.

## Step 3 — 결과 처리

- 에이전트의 verdict·산출물 경로·요약을 터미널에 그대로 전달한다.
- 진단이 상세 설계로 이어지길 원하면 산출물을 `private-senior-be`/`private-senior-dba` 입력으로 연결하도록 안내한다 (아키텍트는 판단·문서까지가 범위).
- 코드 컨벤션 불일치 수정(에이전트 §6)이 포함됐으면 변경 파일을 `/private-review`로 검수하도록 안내한다.

## 보고

> 완료 단언은 `rules/COMPLETION-RULE.md` §1~4를 모두 충족해야 한다.

```
## /private-architect 결과: {in-progress | 완료}
- 산출물: {architecture.md 경로}
- AS-IS 진단: {현재 구조 1줄 + 핵심 병목 건수}
- 트래픽 적합성: {3단계 판정 요약}
- 구조적 해결책: {문제별 채택안 요약}
- 장기 진화 계획: {단계별 분리 + 트리거 조건}
- 다음: {상세 설계로 연결 / 컨벤션 수정 리뷰 안내}
```
