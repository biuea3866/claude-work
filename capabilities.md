# 적합성 프로파일 (Capability Profile)

"어느 LLM이든 메인 세션을 가져간다"를 **검증 가능한 형태**로 만드는 규격. 스킬·그래프는 `requires` 레벨을 선언하고, 런타임은 자기 레벨을 선언한다. 부족하면 중단이 아니라 강등한다.

## 능력 원자 (capability atoms)

| ID | 의미 | 없을 때 무너지는 것 |
|---|---|---|
| `read_file` | 파일 읽기 | 규칙·설계 문서 적용 자체 |
| `write_file` | 파일 쓰기 | 구현·문서 산출 |
| `exec_shell` | 셸 실행 | 테스트·빌드 검증 (완료 단언 불가) |
| `spawn_subagent` | 별도 컨텍스트 에이전트 스폰 | wave 병렬, 독립 검증 |
| `hook_enforce` | 도구 호출 가로채기(사전 차단) | 강제 게이트 — **절차 강제로 대체 필요** |
| `mcp` | MCP 서버 호출 | 외부 연동 스킬 |

## 레벨

| 레벨 | 필요 원자 | 사용 가능 범위 |
|---|---|---|
| **L0** | `read_file` | rules·docs 적용, 코드 리뷰·분석·설계 검수 |
| **L1** | + `write_file`, `exec_shell` | skills 단독 실행, 구현·테스트·검증 |
| **L2** | + `spawn_subagent` | orchestration 병렬 wave, 독립 다중 검증 |

`hook_enforce`와 `mcp`는 레벨과 **직교하는 플래그**다. 레벨이 L2여도 `hook_enforce`가 없으면 차단 게이트는 절차로 대체해야 한다.

## 런타임 매트릭스

각 런타임의 실제 능력은 **`bin/harness doctor`가 탐지해 채운다.** 아래는 선언값이며, `verified` 컬럼이 `probe`인 항목은 doctor 실행 전까지 신뢰하지 않는다.

| 런타임 | 레벨 | `hook_enforce` | `mcp` | verified |
|---|---|---|---|---|
| claude-code | L2 | ✅ (`settings.json` hooks) | ✅ | 확인됨 — 본 하네스의 기준 런타임 |
| codex | L1 | ✅ (`~/.codex/hooks.json`) | ✅ | `spawn_subagent` 여부는 probe |
| gemini-cli | L1 | probe | ✅ | probe |
| cursor | L1 | ✅ (`~/.cursor/hooks.json`) | probe | probe |

> 근거 없이 레벨을 올려 적지 않는다. 확인되지 않은 능력을 전제한 그래프는 런타임에서 조용히 실패한다.

## 강등 사다리

요구 레벨을 못 채울 때 **중단이 아니라** 아래 순서로 내려간다. 강등했으면 그 사실을 산출물 첫 줄에 남긴다.

| 부족한 것 | 강등 경로 |
|---|---|
| `spawn_subagent` (L2 → L1) | 병렬 wave → **같은 세션에서 페르소나 순차 전환**. role 프롬프트를 단계마다 앞에 붙이고 직렬 실행. wave 너비는 로그에만 남기고 실제로는 1 |
| `exec_shell` (L1 → L0) | 검증 자동 실행 불가 → **검증 명령을 사용자에게 제시하고 결과를 입력받는다.** 실행 없이 "테스트 통과"를 단언하지 않는다 |
| `hook_enforce` 없음 | 훅 게이트 → **절차 게이트**. `policy.json`의 `enforcement`별로 대체 경로가 다르다 — `blocking`은 스킬 단계에서 `hooks/<id>.sh`를 직접 호출해 exit code를 확인하고, `ask`는 스킬이 사용자 확인 단계를 명시하며, `advisory`는 생략 가능하다. 각 게이트의 `fallback` 필드가 그 절차를 담는다 |
| `mcp` 없음 | 해당 스킬 단계를 스킵하지 않고 **수동 입력 요청**으로 대체. 스킵은 산출물에 명시 |

## 선언 방법

- **스킬**: frontmatter에 `requires: L1` + `roles: [...]` (사용하는 role 목록). 둘 다 필수 — `bin/harness lint`가 미선언을 오류로 잡는다. 훅 강제가 필요하면 `requires_flags: [hook_enforce]`.
- **그래프 노드**: `requires` + `runtime`/`tier`(바인딩 위임이면 `null`). `bin/harness graph`로 해석값을 확인한다.
- **런타임**: `adapters/<runtime>/capabilities.json`에 선언, `bin/harness doctor`가 실제 탐지와 대조

## 검증

```bash
bin/harness doctor          # 현재 런타임 능력 탐지 + 선언값 대조
bin/harness lint            # 스킬 requires 선언·role 요구 레벨 정합, 바인딩 값, 라우팅 드리프트
bin/harness role <role>     # 그 role 이 어느 런타임·모델로 도는지 + 실행 커맨드
```

> **role 요구 레벨 > 배정 런타임 레벨**인 경우가 있다 — 예: `design.be`(L2)를 codex(L1)에 배정. 이때 `roles.json` 바인딩에 `_degrade`로 강등 경로를 명시해야 하고(없으면 lint 경고), 실제로는 wave 지휘·fanout을 L2 런타임(메인 세션)이 소유한다.
