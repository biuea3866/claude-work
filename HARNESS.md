# HARNESS

`~/.harness`는 **어느 LLM 에이전트가 메인 세션 주도권을 가져가도 동일하게 동작하는** 작업 하네스의 단일 진실 원천(SSOT)이다.

- **version**: 1.0.0
- **SSOT 경로**: `~/.harness` (전역) — 레포별 오버라이드는 `<repo>/.harness`
- **런타임 종속 설정은 여기에 없다.** `policy.json`에서 각 런타임 설정으로 **생성**된다.

## 목적

특정 CLI(Claude Code·Codex·Gemini·Cursor)에 종속되지 않고, 페르소나·규칙·절차·워크플로우를 한 곳에서 정의해 어느 런타임에서든 같은 품질로 실행한다. 런타임은 **실행기**일 뿐이고, 하네스가 **작업 정의**를 소유한다.

## 진입 절차 (모든 에이전트 공통)

세션을 시작한 에이전트는 순서대로 수행한다.

1. **적합성 레벨 판정** — [capabilities.md](./capabilities.md)의 능력 원자표로 자기 레벨(L0/L1/L2)과 훅 강제 가능 여부를 스스로 선언한다.
2. **코어 지침 로드** — `rules/00-core-directives.md`는 **항상** 로드한다 (`scope: always`).
3. **작업별 규칙 선택 로드** — 나머지 `rules/*.md`는 필요한 것만 ID로 참조해 로드한다. 전량 로드는 금지 — 컨텍스트 예산을 태운다.
4. **역할 바인딩 확인** — 스킬·그래프는 **role만** 지정한다. 구체 agent·런타임(claude/codex)·모델은 [roles.json](./roles.json)의 active_profile이 정한다. 해석은 `bin/harness role <role>`(단일) / `bin/harness graph`(그래프 전체)로 하고, 출력의 `invoke`를 그대로 실행한다 — 스킬이 agent 이름·모델을 직접 고르지 않는다 ([ADR 0002](./docs/decisions/0002-llm-runtime-routing.md)).
5. **레벨 부족 시 강등** — 요구 레벨을 못 채우면 중단이 아니라 [강등 사다리](./capabilities.md#강등-사다리)를 따른다. 강등 사실을 산출물에 명시한다.
6. **산출물 기록** — 그래프를 돌 때는 `bin/harness run` 이 상태를 소유한다 (`runs/<run-id>/state.json` 정본, 계약 검증 통과분만 `<node>/result.json`). 상태를 세션 기억에 두지 않는다 ([ADR 0003](./docs/decisions/0003-graph-run-state-machine.md)). 노드를 **실제로 실행**하는 것은 `bin/harness run dispatch`(무인 병렬) 또는 메인 세션의 `invoke`(Agent 툴) 둘 중 하나다 — 어느 경로든 계약 검증을 거친다 ([ADR 0005](./docs/decisions/0005-dispatcher-execution-layer.md)). codex 주간 사용량이 80%에 닿으면 `run next`가 디스패치를 멈추고 `claude-only` 전환 여부를 묻는다 — 임의로 결정하지 않고 사용자에게 올린다 ([ADR 0004](./docs/decisions/0004-runtime-budget-failover.md)).

## 디렉토리 역할

| 경로 | 역할 | 성격 |
|---|---|---|
| `HARNESS.md` | 진입점·버전·우선순위 | 규범 |
| `policy.json` | 권한·샌드박스·승인·게이트 (런타임 중립 SSOT) | 규범 |
| `capabilities.md` | 적합성 레벨(L0/L1/L2)·강등 사다리 | 규범 |
| `roles.json` | role → (agent, runtime, tier, exec.access, verifies) 바인딩 프로파일 + 런타임·모델 카탈로그 | 규범 |
| `rules/` | 검증 가능한 규범(MUST/SHOULD)만 | 규범 |
| `agents/` | 페르소나 정의 — 역할·조건·목표 | 정의 |
| `skills/` | 자연어 호출 절차. 단계는 **role**만 참조 (frontmatter에 `requires`·`roles` 선언) | 정의 |
| `orchestration/` | skills를 엮은 그래프. 노드 = skill + role + runtime/tier + 게이트 | 정의 |
| `orchestration/runner/` | 실행 계층 — 프롬프트 조립·subprocess·wave 병렬·워크트리 | 실행 |
| `orchestration/runner/adapters/` | 런타임 CLI 호출 규칙 (TOML 선언). 새 런타임은 파일 1개 | 정의 |
| `contracts/` | 노드 간 입출력 스키마 — 모델 교체 안전판. `harness run done`이 강제 | 계약 |
| `hooks/` | `.sh` 강제 스크립트. 훅 이벤트 **없이도** CLI 직접 실행 가능해야 함 | 실행 |
| `commands/` | 슬래시 커맨드 | 정의 |
| `mcp/` | MCP 서버 설정 | 정의 |
| `docs/architecture` | 시스템 구조 서술 | 서술 |
| `docs/decisions` | ADR — 왜 그렇게 정했는가 | 서술 |
| `docs/external` | 외부 자료·링크 | 서술 |
| `evals/` | 골든 태스크 + 채점 루브릭 (모델 강등 회귀 검증) | 검증 |
| `adapters/` | 런타임별 투영 빌더 | 실행 |
| `bin/harness` | `build` · `link` · `lint` · `role` · `graph` · `validate` · `run` · `usage` · `doctor` · `eval` · `test` | 실행 |
| `tests/` | 실행 계층·상태 기계 회귀 테스트 (stdlib only). `harness test` 가 돌린다 | 검증 |
| `runs/` | 실행 상태·산출물 — `state.json`·`journal.jsonl`·`<node>/result.json` (gitignore) | 상태 |

### rules vs docs

- `rules/` = **검증 가능한 규범만**. "무엇을 어기면 반려인가"가 명확해야 한다. 검증 불가능한 서술은 넣지 않는다.
- `docs/` = 서술적 맥락. 규범이 아니므로 위반 개념이 없다.

## 우선순위 (충돌 해소)

위에서 아래로 이긴다.

1. 사용자의 명시적 지시 (세션 내)
2. `<repo>/.harness/` — 레포 로컬 오버라이드
3. `~/.harness/rules/00-core-directives.md` — 코어 지침
4. `~/.harness/policy.json` — 권한·게이트
5. `~/.harness/rules/*` — 개별 규칙
6. `agents/` 페르소나 기본값
7. `skills/` 단계 기본값

같은 계층에서 충돌하면 **더 보수적인 쪽**(차단·확인 요구)을 택하고, 충돌 사실을 사용자에게 보고한다.

## 변경 절차

무엇을 바꾸면 무엇을 함께 갱신하고 어떤 명령으로 검증하는가. **표에 있는 갱신을 빼먹으면 드리프트**이고, 대부분 `lint`가 잡는다.

| 변경 | 함께 갱신 | 검증 |
|---|---|---|
| 새 규칙 | `rules/<id>.md` (frontmatter `id`·`scope`·`level`·`context`·`paths`) + `rules/README.md` 목록 | `harness lint` · `harness rules <대상파일>` |
| 새 에이전트 | `agents/<name>.md` (`## 역할 경계`·`## 출력 형식` 필수, `model:` 금지) + `agents/README.md` + 필요 시 `roles.json` role 추가 | `harness lint` · `harness role <role>` |
| 새 스킬 | `skills/<name>/SKILL.md` (frontmatter `requires`·`roles`) + `skills/README.md` | `harness lint` |
| 새 커맨드 | `commands/<name>.md` + `skills/README.md` 커맨드 표 (**`commands/README.md` 금지** — `/README` 커맨드가 생긴다) | `harness lint` |
| 새 훅 | `hooks/<name>.sh` (`chmod +x`, 입력 JSON 자체 가드) + `policy.json` `gates` + `hooks/README.md` | `harness lint` · `harness build` |
| 라우팅 변경 (모델·런타임·프로파일) | `roles.json` `bindings` | `harness graph --sync` → `harness lint` |
| 새 런타임·모델 | `roles.json` `runtimes.<rt>.models/tiers` (+ `verified` 실측) + **`orchestration/runner/adapters/<rt>.toml`** (`[access]` 3등급 필수) + `adapters/README.md` 표 | `harness lint` · `harness test adapter` · `harness role --compact` |
| role 실행 구성·교차 검증 | `roles.json` `roles.<role>.exec` / `.verifies` | `harness lint` · `harness test multiagent` |
| 실행 계층 코드 | `orchestration/runner/*.py` + 해당 `tests/test_*.py` (**테스트 먼저**) | `harness test` |
| 그래프 노드 추가·변경 | `orchestration/<graph>.json` (`runtime`/`tier`는 `null`로 위임) | `harness graph --sync` · `harness lint` |
| 새 계약 | `contracts/<name>.schema.json` + `contracts/README.md` + 필요 시 `semantic_checks()` | `harness validate <계약> <샘플>` |
| 권한·env·게이트 | `policy.json` (시크릿은 `${secrets.KEY}`) | `harness lint` · `harness build --install` |
| **표면 추가·삭제 직후 (필수)** | — | `harness lint && harness test && harness score` — 오류 0 · 테스트 전량 통과 · FAIL 영역 0 확인 |

## 진단 Rubric

하네스 자체의 품질을 영역별로 채점한다. `bin/harness score`가 기계 판정한다.

| 영역 | 배점 | 무엇을 보는가 |
|---|---|---|
| A. 런타임 이식성 | 16 | 머신 절대경로 비의존(하네스 소유 구역), 어댑터·capabilities 선언, 프로파일 전환 가능 |
| B. 완결성 | 14 | 선언한 표면이 실재(lint 오류 0), 핵심 파일 존재 |
| C. 일관성 | 10 | registry README 목록 = 실제 파일, kebab-case, rules frontmatter 스키마 |
| D. 실효성 | 18 | 훅 `bash -n`·자체 가드, **계약 검증기가 실제 위반을 잡는가**, 전 노드 라우팅 해석, eval 자동 채점기, **실 실행 이력** |
| E. 온보딩 | 8 | onboarding 문서, `doctor` 자가진단 |
| F. 유지보수성 | 12 | 변경 절차 표, cross-file drift 검증 수단, SSOT 맵 |
| G. 안전성 | 12 | 시크릿 가드, 파괴적 명령 차단, 모델 SSOT 단일화 |
| H. 문서 정합성 | 10 | 에이전트 필수 섹션, 스킬 선언, `_routing` 주석 최신 |

**채점**: 영역별 통과율 ≥80% → PASS(만점) / 40~80% → PARTIAL(절반) / <40% → FAIL(0).
**게이트**: **FAIL 영역이 2개 이상이면 총점과 무관하게 하네스 신뢰 불가**다. 합격선은 90점.

> **자기 채점의 한계**: Rubric은 기계 판정 가능한 것만 본다. "정의가 실재하는가"는 잡아도 "그 정의가 좋은가"는 못 잡는다. 그래서 D 영역에 *만들어 놓고 안 돌려본 상태*(eval 채점기 부재·실행 이력 없음)를 감점 항목으로 넣어 둔다.

> Rubric은 가변 카운트를 본문에 박지 않는다 — 측정 도구가 스스로 드리프트 원천이 되면 안 된다. 카운트 정본은 각 디렉토리 README다 ([ssot-map](./docs/ssot-map.md)).

## SSOT 규칙 (위반 금지)

- **생성물을 직접 수정하지 않는다.** `~/.claude/settings.json`, `~/.claude/CLAUDE.md`, `~/.codex/config.toml`, `~/.codex/hooks.json`, `AGENTS.md`는 전부 `bin/harness build`의 산출물이다. 고치려면 `policy.json`·`rules/`를 고치고 다시 빌드한다.
- **심링크 대상을 복사본으로 되돌리지 않는다.** `~/.claude/{rules,agents,skills,commands,hooks,mcp}`는 `~/.harness`를 가리키는 심링크다.
- **어댑터는 덮어쓰기가 아니라 병합한다.** `settings.json`에는 Orca 등 외부 도구가 주입한 항목이 공존한다. 어댑터는 **하네스가 소유한 항목만** 교체하고 나머지는 보존한다.
- **모델은 `roles.json`이 단독 소유한다.** `agents/*.md` frontmatter에 `model:`을 넣지 않는다 — 넣으면 그것이 바인딩을 이겨 라우팅이 무력화된다 (lint가 오류로 잡는다).
- 변경 후에는 `bin/harness lint && bin/harness test && bin/harness build && bin/harness doctor`를 돌린다. 라우팅을 바꿨으면 `bin/harness graph --sync`로 그래프 주석까지 갱신한다.

## 참고

- [docs/onboarding.md](./docs/onboarding.md) — 새 머신 복원 (clone → link → build → doctor)
- [docs/ssot-map.md](./docs/ssot-map.md) — 정보별 정본 위치
- [capabilities.md](./capabilities.md) — 적합성 레벨·강등
- [policy.json](./policy.json) — 권한·게이트
- [roles.json](./roles.json) — 역할 바인딩
- [orchestration/README.md](./orchestration/README.md) — 노드 스펙
- [orchestration/runner/README.md](./orchestration/runner/README.md) — 실행 계층 (디스패처·어댑터·워크트리)
- [docs/decisions/0002-llm-runtime-routing.md](./docs/decisions/0002-llm-runtime-routing.md) — 노드별 LLM 배정 (claude ↔ codex 교차 리뷰)
- [docs/decisions/0003-graph-run-state-machine.md](./docs/decisions/0003-graph-run-state-machine.md) — 그래프 실행 상태 기계·계약 강제
- [docs/decisions/](./docs/decisions/) — 설계 결정 이력
