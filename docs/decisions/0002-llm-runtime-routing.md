# ADR 0002 — 노드별 LLM 런타임 배정 (claude ↔ codex 교차 리뷰)

- **날짜**: 2026-08-13
- **상태**: 채택 · 반영 완료 (`roles.json` v2.0.0 · `orchestration/README.md` · `bin/harness lint`)
- **관련**: [roles.json](../../roles.json), [orchestration/README.md](../../orchestration/README.md), [capabilities.md](../../capabilities.md), [ADR 0001](./0001-harness-as-ssot.md)

## 배경

`roles.json`의 `bindings`가 **한 필드에 두 축을 섞고 있었다.** `mixed` 프로파일은 `"prd.author": "codex"`(런타임)와 `"implement.be": "claude-opus-5"`(모델 ID)를 같은 자리에 넣는다. 그 결과:

- 노드가 **어느 LLM에서 도는지** 정의할 자리가 없다. `orchestration/README.md` 노드 스펙 표에 `runtime` 필드가 없다.
- 성능 등급(고차원 작업에 좋은 모델)을 런타임과 독립적으로 표현할 수 없다.

가용 런타임은 2개다. 실측값:

| 런타임 | 레벨 | 선택 가능한 모델 | 호출 경로 |
|---|---|---|---|
| claude | L2 (`spawn_subagent` ✅) | `opus` · `sonnet` · `haiku` · `fable` | `Agent(subagent_type, model)` |
| codex | L1 (`spawn_subagent` ❌) | `sol` · `terra` · `luna` (+ 레거시 5.4·5.4-mini·5.3-codex·5.2-codex) | `codex exec -m … -c model_reasoning_effort=…` (codex-cli 0.147.0) |

## 결정 1 — 축을 분리한다

노드 배정은 **`runtime`(어느 LLM) × `tier`(그 안의 성능 등급)** 두 축으로 표현한다. 한 필드에 섞지 않는다.

## 결정 2 — 작성자와 리뷰어는 서로 다른 런타임

| 산출물 | 작성 | 리뷰 |
|---|---|---|
| 문서 (PRD·TDD·FE/DB 설계·티켓·DAG) | **codex** | **claude** |
| 코드 (구현·마이그레이션·인프라 설정) | **claude** | **codex** |

근거: 같은 모델이 쓰고 같은 모델이 검수하면 **같은 맹점을 공유한다.** 작성 모델이 놓친 것은 그 모델의 리뷰도 놓친다. 작성·리뷰를 교차 배정하면 리뷰가 독립 관측이 된다 — 리뷰 게이트(`REQUEST_CHANGES`)의 존재 이유가 성립한다.

부수 이득: codex는 `hook_stdin_shape`가 미검증이라(`adapters/codex/capabilities.json`) 훅 강제가 조용히 무효화될 위험이 있다. 이 배정에서 codex는 **파일을 쓰지 않는 리뷰**와 **코드 외 문서 작성**만 맡으므로, blocking 게이트 15개가 걸린 코드 경로는 훅이 검증된 claude가 전담한다.

## 결정 3 — 성능 등급 T1/T2/T3

"고차원 작업일수록 좋은 모델"을 등급으로 고정한다. 기준은 **판단 난이도 × 틀렸을 때의 전파 범위**다.

| 등급 | 기준 | claude | codex (모델 + `model_reasoning_effort`) |
|---|---|---|---|
| **T1** | 설계 판단·리뷰 판정. 틀리면 하위 노드 전부가 오염된다 | `opus` | `sol6`(gpt-6-sol) + `high` — 2026-10-07 `sol`(gpt-5.6-sol)에서 상향 |
| **T2** | 규격이 정해진 산출물 생성. 틀려도 그 노드에서 잡힌다 | `sonnet` | `terra` + `medium` |
| **T3** | 기계적 변환. 컨벤션 문서가 답을 이미 갖고 있다 | `haiku` | `luna` + `low` |

**codex는 손잡이가 둘이다** — 모델(sol > terra > luna)과 reasoning effort. 등급은 둘의 조합이며, 한쪽만 움직이지 않는다.

**tier에 배정되지 않은 모델**은 카탈로그에만 두고 **노드 override로만** 쓴다.

| 런타임 | 미배정 모델 | 사유 |
|---|---|---|
| claude | `fable` | 서열 미확정 — opus·sonnet 대비 위치를 eval로 확인하기 전까지 등급에 넣지 않는다 |
| codex | `5.4` · `5.4-mini` · `5.3-codex` · `5.2-codex` | 레거시. `config.toml`이 5.3-codex → 5.4 마이그레이션을 고지 중 |

> **주의 1**: Claude Code `Agent` 툴의 `model` 파라미터는 `opus`/`sonnet`/`haiku`/`fable` **별칭만** 받는다. `claude-opus-5` 같은 전체 ID를 넘기면 거부된다.
> **주의 2**: `gpt-5.6-sol`·`gpt-5.6-luna`는 `gpt-5.6-terra` 패턴에서 **추론한 id**다. 이 머신의 세션 기록에는 terra만 있어 미검증 — `roles.json`에 `verified: false`로 표시했고 lint가 경고를 낸다. 첫 호출 시 확인해 고친다.

## 역할표 (SSOT)

`roles.json`의 role 17개 전부에 대한 배정이다.

| role | 산출물 성격 | runtime | tier | 근거 |
|---|---|---|---|---|
| `prd.author` | 문서 작성 | codex | T1 | (2026-10-07 T2 → T1 상향 — 과제별 PRD 품질) 템플릿 구조가 정해져 있고(`private-prd-template`), 모호점은 질문 목록으로 반환 — 창작이 아니라 정리 |
| `prd.review` | **문서 리뷰** | **claude** | T1 | codex가 쓴 PRD를 교차 검수. 코드베이스와의 충돌 판단이 포함돼 판정 난이도가 높다 |
| `architect` | 문서 작성 | codex | T1 | 구조 진단·바운디드 컨텍스트 판단. 틀리면 이후 전 설계가 잘못된 경계 위에 선다 |
| `design.be` | 문서 작성 | codex | T1 | TDD가 BE·FE·DB 티켓 전부의 입력 |
| `design.fe` | 문서 작성 | codex | T1 | 화면·상태·토큰 설계가 FE 티켓 전부의 입력 |
| `design.db` | 문서 작성 | codex | T1 | 스키마·마이그레이션 순서 오판은 운영 락으로 직결 |
| `design.review` | **문서 리뷰** | **claude** | T1 | codex 설계 3종의 PRD 정합 교차 검수. 사용자 게이트 2의 근거가 된다 |
| `plan.coordinate` | 문서 작성 (티켓·DAG) | codex | T1 | wave 분해 실패 = 병렬성 상실. Single Writer 검증까지 판단 |
| `implement.be` | **코드** | **claude** | T1 | 레이어·캡슐화·TDD 순서 준수가 매 줄 판단. 금지 패턴 30여 개를 동시에 만족해야 함 |
| `implement.fe` | **코드** | **claude** | T1 | 상태 경계·테마 토큰·4상태 처리 판단 |
| `implement.mysql` | 스크립트 | claude | T3 | DDL은 `private-db-schema-convention`이 형식을 확정 — 설계(design.db) 결과의 기계적 전사 |
| `implement.mongodb` | 스크립트 | claude | T3 | 동일 — 컬렉션·인덱스·validator 전사 |
| `implement.kafka` | 설정·계약 | claude | T3 | 토픽 명명·파티션·계약 md 형식이 컨벤션에 고정 |
| `implement.redis` | 설정·계약 | claude | T3 | 키 스키마·TTL 표 작성. 판단은 design 단계에서 끝남 |
| `review.code` | **코드 리뷰** | **codex** | T1 | claude가 쓴 코드를 교차 검수. p0~p2 판정이 wave 게이트를 막는다 |
| `review.infra` | **코드 리뷰** | **codex** | T1 | 동일 — 마이그레이션·토픽·키 설계 교차 검수 |
| `qa` | 실행 검증 | claude | T2 | 브라우저 MCP·dev 실구동이 필요해 실행 능력이 배정 기준. 독립 검증은 `review.code`(codex)가 이미 담당 |

**교차 규칙 검증**: 문서 작성 6개(`prd.author`·`architect`·`design.be/fe/db`·`plan.coordinate`)는 전부 codex, 그 리뷰 2개(`prd.review`·`design.review`)는 전부 claude. 코드 작성 6개(`implement.*`)는 전부 claude, 그 리뷰 2개(`review.code`·`review.infra`)는 전부 codex. 자기 산출물을 자기가 검수하는 경로는 없다.

## 그래프 노드 매핑

`orchestration/private-feature.json` 9개 노드에 위 표를 적용한 결과다.

| 노드 | role | runtime | tier |
|---|---|---|---|
| `prd` | `prd.author` | codex | T1 |
| `prd-review` | `prd.review` | claude | T1 |
| `design-be` | `design.be` | codex | T1 |
| `design-db` | `design.db` | codex | T1 |
| `design-fe` | `design.fe` | codex | T1 |
| `design-review` | `design.review` | claude | T1 |
| `plan` | `plan.coordinate` | codex | T1 |
| `implement` (fanout) | `implement.*` — 티켓의 `role` 필드로 결정 | claude | BE/FE T1 · DB/INFRA T3 |
| `review` | `review.code` | codex | T1 |

파이프라인은 **런타임이 6회 교대**한다: codex → claude → codex×3 → claude → codex → claude → codex.

**그래프에는 하드코딩하지 않는다.** 노드의 `runtime`/`tier`는 `null`(프로파일 위임)로 두고, 해석 결과를 `_routing` 주석으로 드러낸다. 하드코딩하면 `claude-only`·`portable` 프로파일이 무력화된다 — 노드 override는 그 노드만 예외일 때만 쓴다. 주석은 `harness graph --sync`가 채우고, 바인딩이 바뀌면 lint가 stale로 잡는다.

**fanout 라우팅** — 티켓 접두사(BE/FE/DB/INFRA)로 role을 유추할 수 없다. `DB`는 mysql/mongodb, `INFRA`는 kafka/redis로 갈려 1:1이 아니다. 그래서 `contracts/design-doc.schema.json`의 `tickets[]`에 `role`을 **필수 필드로 추가**하고, 노드는 `fanout.role_from: "role"`로 그 값을 읽는다. `fanout.roles`는 후보 목록으로 정적 검증의 근거가 된다.

## 실행 경로

해석은 `bin/harness role <role>`이 담당하고, 출력의 `invoke`가 실행 형식의 SSOT다. 스킬은 그 문자열을 그대로 실행한다.

- **claude 노드**: `Agent(subagent_type=<agent>, model=<tier 별칭>)`.
- **codex 노드**: codex는 서브에이전트 개념이 없어 **페르소나를 프롬프트로 주입**해야 한다 — `agents/<agent>.md`를 stdin으로 흘려보내고 과업을 이어 붙인다.

  ```bash
  { cat ~/.harness/agents/private-senior-be.md; echo; echo "<프롬프트>"; } \
    | codex exec -m gpt-5.6-sol -c model_reasoning_effort=high \
        -s workspace-write -C <worktree> --skip-git-repo-check -
  ```

  `-s workspace-write`를 고정한다 — 문서 산출물을 파일로 써야 하고, `danger-full-access`는 쓰지 않는다. `codex exec`는 **별도 세션이라 컨텍스트를 물려받지 않으므로**, 입력·산출 경로와 계약을 프롬프트에 전부 적고 산출물을 파일로 받는다.
- **orca 경로**: `/private-feature-orca`는 `roles.json` 해석을 orca worker 플래그로 옮긴다 — `runtime` → `--agent claude|codex`, `tier` → `--model`/`--effort`. 배정 표를 자기 문서에 복제하지 않는다.
- **메인 세션은 claude가 가져간다.** codex는 L1이라 `spawn_subagent`가 없어 `implement` fanout(wave 병렬)을 스스로 열 수 없다. fanout 소유권은 L2 런타임에 두고, codex 노드는 **단발 호출로 소비**한다. codex가 메인을 잡는 구성도 가능하지만 그때는 [강등 사다리](../../capabilities.md#강등-사다리)에 따라 wave가 직렬이 된다.

## 대안과 미채택 사유

| 대안 | 미채택 사유 |
|---|---|
| 전 노드 claude 단일 런타임 | 작성·리뷰가 같은 맹점을 공유한다. 리뷰 게이트가 형식이 된다 |
| 전 노드 codex 단일 런타임 | L1 — `spawn_subagent` 없음. wave 병렬이 전부 직렬로 강등된다 |
| `model` 한 필드에 런타임·모델을 계속 혼용 | 노드별 런타임 지정이 불가능하고, lint가 값을 검증할 수 없다 (배경 참조) |
| 등급 없이 전부 최고 성능 모델 | T3 4개(전사 성격)에 T1을 쓰는 비용이 매 wave 반복된다 |
| 리뷰까지 T2로 내려 비용 절감 | 리뷰는 게이트다 — 오판정이 곧 하자 통과. 등급을 내리려면 `evals/`로 회귀를 먼저 증명해야 한다 |

## 파급 (반영 완료)

**`roles.json` v2.0.0** — 바인딩 값이 문자열에서 `{runtime, tier}` 객체가 됐다. 구 프로파일 `default`·`budget`·`mixed`는 폐기하고 3개로 재구성했다.

| 프로파일 | 용도 |
|---|---|
| `cross-review` (active) | 이 ADR의 역할표 |
| `claude-only` | codex 미설치·미인증 환경. 교차 리뷰 이점을 잃으므로 리뷰 노드는 T1 유지 |
| `portable` | 등급 지정을 지원하지 않는 런타임 — `host` 런타임으로 전부 위임 |

구 `mixed` 프로파일 대비 실제로 바뀐 것:

| role | 구 `mixed` | 현행 | 성격 |
|---|---|---|---|
| `prd.review` | codex | **claude** | 교차 규칙 위반 시정 — codex가 쓴 PRD를 codex가 검수했다 |
| `design.review` | codex | **claude** | 교차 규칙 위반 시정 |
| `implement.mysql/mongodb/kafka/redis` | `_fallback` → opus | claude **T3** | 등급 과다 시정 |
| `architect`·`qa` | 미바인딩 | 명시 배정 | 누락 보완 |

**`_default` 의무화** — 프로파일마다 `_default`가 있어야 한다. 구 `_fallback`은 스펙 어디에도 정의가 없던 관례였고, 이제 lint가 부재를 오류로 잡는다.

**`orchestration/README.md`** — 노드 스펙에 `runtime`·`tier` 행을 추가했다. `private-feature.json` 9개 노드의 `model: null`은 `runtime: null` + `tier: null`로 교체했다(= 바인딩 위임).

**`bin/harness lint`** — 바인딩 **값**을 검증한다. 결함 8종 주입 테스트로 전부 검출 확인(exit 1):

| 검사 | 대상 |
|---|---|
| 존재하지 않는 runtime | `{"runtime": "gpt-9"}` |
| 잘못된 tier | `T9` |
| 구 포맷(문자열) 바인딩 | `"codex"` |
| 카탈로그에 없는 모델을 가리키는 tier | `tiers.T2.model = "gpt-4o"` |
| `_default` 누락 | 프로파일 전체 |
| 폐기된 `model` 필드 | 그래프 노드 |
| runtime/tier 한쪽만 지정한 override | `{"runtime":"codex","tier":null}` |
| role.requires > runtime.level 인데 `_degrade` 없음 | 경고 (강등 경로 명시 요구) |

**실행 층까지 연결 완료** — 정의만 있고 실행이 타지 않던 문제를 닫았다.

| 층 | 이전 | 현재 |
|---|---|---|
| `agents/private-*.md` frontmatter | `model:` 17개가 바인딩을 **이기고 있었다** (claude 배정 role 7건 불일치) | 전부 제거. `roles.json`이 모델을 단독 소유하고, frontmatter에 `model:`이 있으면 lint 오류 |
| 스킬 5개 + orca 커맨드 | `Agent(private-X)` 직접 호출 18건 → 바인딩 무시 | role 참조로 전환. frontmatter에 `requires`·`roles` 선언, 본문 상단에 `harness role --compact` 라우팅 표 |
| codex 실행 경로 | 없음 (`codex exec` 호출 0건) | `harness role`의 `invoke`가 페르소나 주입 형식까지 생성 |
| 해석 도구 | 없음 | `harness role` / `harness graph` |

**경로 주의** — 스킬의 `!` 치환은 **프로젝트 cwd**에서 실행된다. `bin/harness`(상대경로)로 쓰면 깨지므로 `~/.harness/bin/harness`로 적어야 하고, lint가 상대경로 호출을 오류로 잡는다.

## 미결

- **`gpt-5.6-sol` · `gpt-5.6-luna` id 미검증.** terra 패턴에서 추론한 값이라 첫 호출 때 확인해야 한다. lint가 경고 2건으로 남긴다.
- **codex 등급 차이의 실효성 미검증.** 모델(sol/terra/luna) × `model_reasoning_effort`(high/medium/low) 조합이 T1/T2/T3 구분으로 충분한지 `evals/` 골든 태스크로 확인 전이다. 그 전까지 이 등급 배정은 **가설**이다 (`evals/README.md`의 문제의식과 동일).
- **`fable` 위치 미확정.** 카탈로그에만 두고 tier에 넣지 않았다. eval로 opus·sonnet 대비 위치를 재면 등급에 편입한다.
- **codex 훅 stdin shape 미검증.** shape가 다르면 게이트가 조용히 exit 0으로 빠진다. 이 배정은 codex를 쓰기 경로에서 뺐지만, codex가 메인 세션을 잡는 구성에서는 여전히 위험이다.
- **`prd.author` 는 2026-10-07 T1(sol6 = gpt-6-sol · high)로 상향했다. `qa` T2는 조정 여지가 있다.** 산출물 품질이 낮으면 T1으로 올린다 — 판단 근거는 eval 리포트로 남긴다.
