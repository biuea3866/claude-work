# 완료 단언 규칙 (Completion Assertion Rule)

모든 PIPELINE.md 가 공통으로 따르는 "완료" 단언 룰. 운영 사고(Kafka SCRAM 누락, 잘못된 update 라인, "완벽하게 테스트" 거짓 단언) 재발 방지.

## 거짓 완전성 차단 (False Completeness Block)

다음 중 하나라도 충족 안 되면 **"완료 / 다 했다 / 검증 끝"** 같은 단언 금지. 충족 안 된 항목이 있는 상태는 항상 `in-progress` 로 보고.

### 1. 강제 산출물 (Mandatory Deliverables)

각 PIPELINE.md 의 "강제 산출물" 섹션에 명시된 모든 파일이 존재하고 비어 있지 않아야 한다. 1개라도 빠지면 `in-progress`.

산출물 경로 형식:
```
outputs/<name>/<YYYYMMDD>-<topic>/<file>.md
```

빈 placeholder 금지. 각 산출물에는 측정값/근거/링크가 들어가야 한다.

### 2. 검증 아티팩트 (Verification Artifacts)

"테스트 통과 / 빌드 성공 / 동작 확인" 같은 단언은 다음 중 1개 이상의 아티팩트를 같은 메시지에 첨부해야 인정.

| 단언 | 필요 아티팩트 |
|------|---------------|
| "테스트 통과" | `./gradlew test` raw 출력 / `gh run view <id>` 링크 / 커버리지 리포트 경로 |
| "빌드 성공" | 빌드 raw 출력 / CI run 링크 |
| "쿼리 동일" | EXPLAIN diff / Hibernate SQL 로그 diff / 데이터 spot check |
| "전 레포 적용" | `outputs/multi-repo/<...>/03-progress.md` 의 done/pending 표 |
| "동작 동일" | `outputs/refactor/<...>/diff-verification.md` 의 ✅ 표 |
| "보안 검토 완료" | `gh pr review` 코멘트 / senior-gate.py raw 출력 |
| "PRD 분석 완료" | `outputs/analyze-prd/<...>/requirements.md` + `acceptance.md` |

### 3. 도구 호출 선행 (Tool Call Precedence)

단언 텍스트보다 **먼저** 도구 호출이 transcript 에 있어야 한다. 즉:

```
✅ 올바른 순서:
[Bash] ./gradlew test → 출력 캡처
[Text] "테스트 통과 — 위 출력 참조"

❌ 잘못된 순서:
[Text] "테스트 통과했습니다"
(이후 도구 호출 없음 — 사용자가 '했어?' 라고 물어야 그제서야 실행)
```

### 4. "지금 시작" 도 금지된 단언

"지금 적용하겠습니다 / 다음에 하겠습니다 / 곧 처리됩니다" 도 산출물 없이 단언 금지. 의도만으로는 in-progress 도 아니고 todo 항목으로만 남길 것.

## 진단·점검

`process-reviewer` 에이전트가 메타-피드백 트리거 #5 (claim-without-action) 로 다음 패턴을 감지:

- 단언 메시지 ± 600초 내에 동일 주제 도구 호출 없음
- "완료/통과/검증" 키워드 + 아티팩트 없음
- 사용자의 "했어?" / "확인했어?" 질문 직후 도구 호출이 발생 (선단언 후실행 패턴)

검출 시 `docs/feedback-loop/proposals/<YYYYMMDD>-claim-without-action.md` 자동 생성.

## 적용

이 규칙은 모든 PIPELINE.md 의 마지막 단계 ("회고" 또는 그 직전) 에서 다음 1줄로 명시 참조:

```
> 완료 단언은 `rules/COMPLETION-RULE.md` 의 §1~4 를 모두 충족해야 한다.
```

## 참고

- 운영 사고 사례: REFACTOR.md §7 안티패턴 "거짓 완전성 (False completeness)"
- 메타-피드백 트리거: `commands/audit-feedback-loop.md`
- 가디언 효과 측정: `agents/feedback-loop-guardian.md`
