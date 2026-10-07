# 제안 — `#subagent-report-write-blocked` (2회 반복)

## 근거 run
- `runs/private-implement/20261007-interview-patch-ownership/retro.md:26` — analyze.context(claude) 서브에이전트의 `analysis-A.md` Write 거부, 텍스트 반환본을 메인 세션이 저장
- `runs/private-implement/20261007-orca-session-dashboard/retro.md` — 동일 현상 재현 ("서브에이전트 정책"으로 `analysis-A.md` 저장 실패, 메인 세션이 원문 저장)

## 현상
- `agents/private-context-analyst.md` 는 `tools: … Write` 를 갖지만, claude 서브에이전트로 실행되면 run 디렉토리(`~/.harness/runs/...`)에 보고서 파일 쓰기가 거부된다.
- codex 쪽(analyze.cross)은 `--add-dir <run>` 으로 같은 경로에 정상 기록 — 런타임 간 산출 방식이 비대칭.
- 매번 메인 세션이 수천 자를 다시 써야 해 컨텍스트·시간 낭비, 옮겨 적는 과정에서 원문 훼손 위험.

## 수정안 (둘 중 택1)
1. **스킬 계약화 (권장, 최소 변경)** — `skills/private-implement/SKILL.md` Step 1 에 명시:
   "claude 런타임 분석가는 보고서를 **최종 메시지 텍스트로 반환**하고, 메인 세션이 그 원문을 `analysis-A.md` 로 저장한다 (가공 금지)." 분석가 프롬프트에서 Write 지시를 빼 실패 왕복을 없앤다.
2. **권한 해소** — 서브에이전트 Write 거부 원인(정책/훅)을 찾아 run 디렉토리를 허용 경로에 추가. 원인 조사 필요, 영향 범위 큼.

## 반영 절차
- 사용자 승인 후 `~/.harness` 에서 별도 브랜치·PR 로 반영 (대상 PR 과 섞지 않음).

## 반영
- 2026-10-07 사용자 승인 → 수정안 1 (스킬 계약화) 반영
