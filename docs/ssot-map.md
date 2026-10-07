# SSOT 맵 — 이건 어디서 고치나

정보마다 **정본이 하나**다. 같은 사실이 두 곳에 적히면 반드시 드리프트한다. 아래 표에 없는 곳에서 값을 고쳤다면 그건 생성물이거나 복제본이다.

## 정의

| 정보 | 정본 | 검증 |
|---|---|---|
| 최상위 행동 규칙 (TDD·완료 단언) | `rules/00-core-directives.md` | `harness lint` |
| 코드 컨벤션·리뷰 기준·템플릿 | `rules/<id>.md` (frontmatter `id`·`paths`) | `harness rules <파일>` |
| 어느 규칙이 어느 파일에 적용되는가 | 각 규칙의 frontmatter `paths` | `harness rules` |
| 페르소나 (역할·경계·출력 형식) | `agents/<name>.md` | `harness lint` (필수 섹션) |
| **role → agent 바인딩** | `roles.json` `roles` | `harness role` |
| **role → 런타임·모델 (라우팅)** | `roles.json` `bindings.<profile>` | `harness role` · `harness graph` |
| 런타임별 모델 카탈로그·등급 | `roles.json` `runtimes.<rt>.models/tiers` | `harness lint` |
| 파이프라인 단계 순서·의존·게이트 | `orchestration/<graph>.json` | `harness graph` |
| 노드 산출물 스키마 | `contracts/*.schema.json` | `harness validate` |
| **role 실행 구성 (접근 등급·도구)** | `roles.json` `roles.<role>.exec` | `harness lint` |
| **누가 누구를 검증하는가 (교차 리뷰)** | `roles.json` `roles.<role>.verifies` | `harness lint` |
| **런타임 CLI 호출 규칙 (argv 조립)** | `orchestration/runner/adapters/<rt>.toml` | `harness lint` · `harness test adapter` |
| 접근 등급 → 런타임 네이티브 키 번역 | 같은 파일 `[access]` | `harness lint` |
| 런타임 소진 감지 패턴 | 같은 파일 `[failover]` | `harness test adapter` |
| 노드 실행 (프롬프트 조립·프로세스) | `orchestration/runner/dispatch.py` | `harness test dispatch` |
| 티켓 wave·워크트리 배치 | `orchestration/runner/wave.py` | `harness test wave` |
| 스키마로 표현 못 하는 산출물 규칙 | `bin/harness` `semantic_checks()` | `harness validate` |
| 권한·게이트·env | `policy.json` | `harness lint` |
| **시크릿 실값** | `secrets.local.json` (gitignore) | `harness lint` (평문 금지) |
| 적합성 레벨·강등 사다리 | `capabilities.md` | `harness doctor` |
| 런타임 실제 능력 | `adapters/<rt>/capabilities.json` | `harness doctor` |
| 하네스 품질 기준 | 본 저장소 `HARNESS.md` §진단 Rubric | `harness score` |

## 카운트 (숫자가 필요할 때)

| 대상 | 정본 |
|---|---|
| 규칙 목록·수 | `rules/README.md` |
| 에이전트 목록·수 | `agents/README.md` |
| 스킬·커맨드 목록 | `skills/README.md` |
| 훅 목록 | `hooks/README.md` |
| 계약·그래프 목록 | `contracts/README.md` · `orchestration/README.md` |
| 런타임 어댑터 목록 | `orchestration/runner/adapters/README.md` |
| 테스트 목록·건수 | `harness test` 출력 (파일이 스스로 판정) |

**상위 문서(`HARNESS.md`·`capabilities.md`·본 문서)는 가변 카운트를 적지 않는다.** 측정 도구가 스스로 드리프트 원천이 되지 않게 하기 위함이고, `harness lint`가 하드코딩된 카운트를 경고로 잡는다. 예외는 ADR — 그건 시점 기록이라 그때의 실측치를 남긴다.

## 생성물 (직접 고치지 않는다)

| 생성물 | 원본 | 재생성 |
|---|---|---|
| `~/.claude/settings.json` | `policy.json` + `secrets.local.json` | `harness build --install` |
| `~/.claude/CLAUDE.md` | `rules/00-core-directives.md` | `harness build --install` |
| `~/.codex/hooks.json` · `AGENTS.md` | `policy.json` | `harness build --install` |
| 그래프 노드의 `_routing` 주석 | `roles.json` 바인딩 | `harness graph --sync` |
| `~/.claude/{rules,agents,skills,commands,hooks,mcp}` | `~/.harness/*` (심링크) | `harness link --install` |
| `runs/<run-id>/**` | 실행 이력 | 재생성 안 함 (append-only) |

## 규칙 컨텍스트

`rules/`의 규칙은 `context` 로 갈린다 — `common`(런타임·프로젝트 무관)과 `private`(개인 프로젝트 전용). 로드는 항상 선택적으로 한다.

```bash
bin/harness rules <대상파일> --context private
```

전량 로드는 금지다 — 컨텍스트 예산은 저가·소형 모델 노드에서 곧바로 병목이 된다.

## 참고

- [HARNESS.md](../HARNESS.md) — 진입 절차·우선순위·변경 절차
- [decisions/0002](./decisions/0002-llm-runtime-routing.md) — 라우팅 SSOT가 왜 `roles.json` 하나여야 하는가
- [decisions/0003](./decisions/0003-graph-run-state-machine.md) — 실행 상태 SSOT가 왜 `runs/state.json`인가
