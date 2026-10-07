# contracts — 노드 간 입출력 계약

그래프의 노드마다 에이전트·모델이 다르다. 엣지가 **앞 노드의 산문**이면 모델을 바꾸는 순간 품질이 조용히 무너진다. 계약은 그걸 막는 안전판이다.

## 원칙

- 노드는 `output_contract`를 선언하고, 종료 시 산출물이 그 스키마를 만족하는지 검증한다.
- **검증 실패는 재시도 사유**다 (`retry.on: ["contract_violation"]`). 조용히 통과시키지 않는다.
- 스키마는 **의미 있는 필드**를 강제한다. `{"result": "string"}` 같은 계약은 계약이 아니다.
- 사람이 읽을 산문은 `summary_md` 필드에 담고, 기계가 분기할 값은 별도 필드로 뺀다. 뒤 노드가 산문을 파싱하게 두지 않는다.

## 스키마 목록

| 파일 | 쓰는 노드 | 핵심 강제 |
|---|---|---|
| `review-verdict.schema.json` | `review.code`, `review.infra`, `prd.review`, `design.review` | verdict enum + 발견 항목의 `file:line` + 등급 |
| `design-doc.schema.json` | `design.be`, `design.fe`, `design.db` | 필수 섹션 존재 + 티켓 DAG + wave 너비 |
| `implementation-result.schema.json` | `implement.*` | 검증 아티팩트 필수 — 완료 단언 규칙의 기계적 강제 |

## 검증

```bash
bin/harness validate contracts/<schema>.json <result.json>   # 스키마 + 의미 규칙
bin/harness run done <node> --result <result.json>           # 위 검증을 통과해야 completed
bin/harness lint                                             # output_contract 참조가 실재하는지
```

검증기는 **외부 의존성 없이** draft 2020-12의 사용 부분집합을 구현한다 — `type`·`required`·`properties`·`additionalProperties:false`·`enum`·`pattern`·`minLength`·`minItems`·`minimum`·`maximum`·`uniqueItems`·`items`.

### 스키마로 표현 못 하는 규칙 (semantic checks)

스키마 통과가 곧 규칙 준수는 아니다. 아래는 `harness validate`가 **계약 위반과 같은 무게로** 잡는다.

| 계약 | 규칙 |
|---|---|
| `implementation-result` | `status=done` 인데 `exit_code≠0`·미실행·아티팩트 없음 (COMPLETION-RULE §1~2) / `red_first=false` 또는 증거 없음 (core-directives §1) |
| `review-verdict` | findings 등급 ↔ verdict 불일치 / `files_read < files_changed` 인데 skipped 사유 없음 |
| `design-doc` | 모든 wave 너비 1~2 (직선형 DAG = 분해 실패) / 같은 wave 파일 교집합 (Single Writer) / `depends_on`이 같거나 뒤 wave를 가리킴 / wave 누락·미존재 티켓 참조 / `max_wave_width` 불일치 |

상세: [ADR 0003](../docs/decisions/0003-graph-run-state-machine.md)
