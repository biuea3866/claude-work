---
description: 서브에이전트 스폰 ledger를 분석해 wave 병렬/직렬을 사후 감사한다. 직렬화 의심 시 근거와 함께 리포트하고 원인 점검을 안내한다.
---

# /wave-audit — Wave 병렬 실행 감사

## 입력
`$ARGUMENTS` (선택) — ledger 경로 / `--gap <초>` / `--dag <tpm-analysis.md 경로>`. 없으면 가장 최근 ledger + 기본 gap 20초.

## 무엇을 하는가

`custom-wave-spawn-log.sh`(PreToolUse Task|Agent hook)가 적재한 스폰 타임스탬프 ledger를 분석해, 같은 wave로 묶였어야 할 서브에이전트들이 **직렬로 스폰됐는지** 탐지한다.

- **병렬**: 한 어시스턴트 메시지의 multi-tool-use → 수초 내 군집 (큰 wave 너비)
- **직렬**: 앞 에이전트 완료를 기다려 다음을 스폰 → 분 단위 간격 (너비 1 wave 반복)

## 실행

```bash
python3 "$HOME/.claude/hooks/lib/wave-audit.py" $ARGUMENTS
```

DAG와 대조하려면 해당 세션의 `tpm-analysis.md`를 넘긴다:

```bash
python3 "$HOME/.claude/hooks/lib/wave-audit.py" --dag .analysis/outputs/{날짜}_{기능명}/tpm-analysis.md
```

## 판정 후 처리

- **병렬 양호** → 그대로 보고.
- **직렬화 의심** → 리포트를 출력하고 다음 3개 원인을 점검한다:
  1. **오케스트레이터 규율**: ready 셋을 한 메시지에 N개 tool_use로 동시 스폰했는가 (여러 메시지로 나누면 직렬화)
  2. **worktree 격리**: 병렬 스폰 시 `isolation: "worktree"`를 썼는가 (안 쓰면 `.git/index.lock` 충돌로 사실상 직렬)
  3. **분해 품질**: DAG 자체가 직선형은 아닌가 (prd-reviewer 게이트에서 걸렀어야 함 — `ticket-guide.md` "Fan-out 너비 목표")

직렬화가 분해 탓이면 `tpm` 재분해, 실행 탓이면 다음 wave부터 한 메시지 동시 스폰으로 교정한다.

## 한계

이 감사는 **탐지·피드백**이지 사전 차단이 아니다. 스폰 시점에는 "한 메시지에 묶였는지"를 알 수 없어(단일 tool_use 단위로만 hook이 발동) 사후 타임스탬프로 판정한다. gap 임계값(기본 20초)은 에이전트 실행 시간이 그보다 짧으면 오탐할 수 있으니 `--gap`으로 조정한다.
