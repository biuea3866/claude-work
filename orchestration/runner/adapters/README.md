# adapters — 런타임 선언

각 파일이 LLM CLI 하나를 어떻게 부르는지 선언한다. **러너 코드에는 런타임 이름 분기가 없다** —
새 런타임을 붙이려면 여기에 TOML 1개만 추가한다.

| 파일 | 런타임 | 결과 회수 | 특징 |
|---|---|---|---|
| `claude.toml` | Claude Code CLI (`claude -p`) | stdout JSON 봉투 | 프로젝트 MCP 를 붙일 수 있는 유일한 런타임. 비용 회수 가능 |
| `codex.toml` | Codex CLI (`codex exec`) | `-o` 출력 파일 | `--output-schema` 로 출력 형식 강제 가능 |

`host` 런타임에는 어댑터가 없다 — 현재 세션 런타임이라 부를 subprocess 가 없다. 디스패처는
그 노드를 "수동 실행 필요"로 보고한다.

## 스키마

| 키 | 필수 | 의미 |
|---|---|---|
| `id` | ✅ | 런타임 식별자. **`roles.json#runtimes` 의 키와 일치**해야 한다 (`harness lint` 가 대조) |
| `base` | ✅ | 항상 붙는 argv 접두 |
| `prompt_delivery` | ✅ | `stdin` \| `argv` |
| `result` | ✅ | `stdout_envelope` \| `out_file` |
| `envelope_result_key` | — | 봉투에서 결과를 꺼낼 키 (`stdout_envelope` 일 때) |
| `envelope_cost_key` | — | 비용 키. 없으면 비용 미집계 |
| `envelope_error_key` | — | 오류 플래그 키. **CLI 가 API 오류에도 exit 0 을 내므로** 종료 코드만 보면 실패를 성공으로 오판한다 |
| `[env]` | — | 자식 프로세스 환경 — `unset` 배열 · `set` 맵. 부모 셸은 건드리지 않는다 |
| `[defaults]` | — | 노드가 값을 안 줬을 때의 기본값 |
| `[flags]` | — | 노드 키 → argv 조각 |
| `[runtime]` | — | 러너가 채우는 슬롯 — `out_file` · `cwd` |
| `[access]` | ✅ | 접근 등급 → 런타임 네이티브 키 번역 |
| `[failover]` | — | 소진 시 대체 런타임 |

### `[flags]` 자리표시자

| 표시자 | 치환 |
|---|---|
| `{value}` | 노드 값 그대로 |
| `{csv}` | 리스트를 쉼표로 연결 (리스트가 아니면 실행 전 실패) |
| `{root_path}` | 하네스 루트 기준 경로로 풀고 **존재를 검증**한다 |

**`[flags]` 에 없는 키를 노드가 들면 실행 전에 죽는다.** 조용히 무시하면 안전 의미(권한·샌드박스)가
사라진 채 돈다.

### `[access]` — 접근 등급 번역

`roles.json#roles[].exec.access` 는 런타임 중립 등급 3개만 안다. 번역표가 여기 있다.

| 등급 | claude | codex |
|---|---|---|
| `read-only` | `permission_mode = dontAsk` | `sandbox = read-only` |
| `workspace-write` | `permission_mode = acceptEdits` | `sandbox = workspace-write` |
| `full` | `permission_mode = bypassPermissions` | `sandbox = danger-full-access` |

`full` 이 `bypassPermissions` 인 이유: `acceptEdits` 는 Bash 를 샌드박스해 워크스페이스 밖 쓰기를
막는다. 빌드 도구(Gradle·npm)는 홈 캐시에 잠금·소켓을 만들어야 하므로 그 모드에서는 빌드가
시작조차 못 한다. 테스트를 못 돌리면 "통과" 단언에 근거가 없어
[COMPLETION-RULE](../../../rules/COMPLETION-RULE.md) 위반이다.
어느 등급에서도 `hooks/` 가드(시크릿·push·파괴적 연산)는 그대로 적용된다.

### `[failover]`

| 키 | 의미 |
|---|---|
| `fallback_to` | 대체 런타임 id. 없는 id·자기 자신이면 **로드 시점에 실패** |
| `fallback_model` | 대체 런타임의 모델 id (노드 모델은 원 런타임 전용이라 못 넘긴다) |
| `exhaustion_patterns` | stdout+stderr 에 대소문자 무시로 검사하는 정규식 배열 |
| `[failover.translate.<key>.<value>]` | 런타임 전환 시 키·값 명시 변환 |

패턴은 **관측에서 나온다.** 추측으로 넣지 않는다 — 각 패턴 옆에 어떤 문구를 잡으려는지 주석을 남긴다.
문구가 하나 빠지면 그 종류의 소진이 감지되지 않고 노드가 한도까지 태우고 전멸한다.

### `[env]` — 자식 프로세스 환경

```toml
[env]
unset = ["ANTHROPIC_API_KEY"]
set = { SOME_FLAG = "1" }
```

claude 어댑터가 `ANTHROPIC_API_KEY` 를 지우는 이유: 그 키가 있으면 CLI 가 claude.ai 로그인
대신 키를 쓰고, 키에 크레딧이 없으면 **모든 claude 노드가 실패**한다 (2026-08-27 실측 —
헤드리스 호출 전량 `Credit balance is too low`, 키를 걷어내면 정상). 부모 셸 환경은
바뀌지 않는다.

## 새 런타임 추가 절차

1. `adapters/<id>.toml` 작성 — 위 스키마의 필수 키 + `[access]` 3등급.
2. `roles.json#runtimes` 에 같은 `id` 로 모델·등급 등록.
3. `harness lint` — 어댑터↔런타임 정합·접근 등급 번역 존재를 검사한다.
4. `harness test adapter` — argv 조립·소진 감지 회귀 확인.
5. `harness run dispatch --dry-run` — 조립 결과를 실행 없이 확인.

**러너 코드는 고치지 않는다.** 고쳐야 한다면 그건 어댑터 스키마에 표현력이 부족하다는 신호다.
