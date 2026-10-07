# hooks — 개인 하네스 훅

각 훅은 git tracked 셸 스크립트다. 등록은 `policy.json` 의 `gates` 가 SSOT이고, `~/.claude/settings.json` 은 `bin/harness build` 의 생성물이다 — 런타임 설정을 직접 고치지 않는다.

모든 훅은 `bash -n` 통과를 전제로 하고, 추가 시 `chmod +x` 가 필수다.

## 스코프 두 가지

| 스코프 | 판정 | 대상 |
|---|---|---|
| **전역** | 모든 레포에서 동작. 프로젝트가 같은 이름의 훅을 자체 등록했으면 비켜선다 (`lib/global-hook-guard.sh`) | 시크릿·git·MCP·worktree 가드 |
| **개인 프로젝트 전용** | 레포 루트에 마커 `.claude/private-project` 가 있을 때만 동작 (`lib/private-project-guard.sh`) | 컨벤션·배포·머지 게이트 |

마커는 **레포에 커밋**해 둔다 — 에이전트가 만드는 격리 worktree 체크아웃에도 있어야 훅이 동작한다.

## 등록된 훅 (14개)

### 전역 가드 (8개)

| 파일 | 시점 | matcher | 동작 | 차단? |
|---|---|---|---|---|
| `private-block-env-read.sh` | PreToolUse | `Bash` | `cat`/`grep`/`vi` 등 + `.env*`·`*.pem`·`id_rsa` / `echo $TOKEN` / `printenv` / `env` 차단 | ✅ |
| `private-secrets-read-guard.sh` | PreToolUse | `Read` | `Read` 도구로 `.env`·credentials·`*.pem` 읽기 차단 (`.env.example`·`.sample`·`.template` 허용) | ✅ |
| `private-secrets-edit-guard.sh` | PreToolUse | `Edit\|Write\|MultiEdit` | `.env`·credentials·`*.pem` 편집 차단, 설정 파일의 비밀 패턴 경고 | ✅ |
| `private-block-git-push.sh` | PreToolUse | `Bash` | `git push --force`/`--force-with-lease` 직전 사용자 승인 프롬프트 | 🔔 (ask) |
| `private-require-self-review.sh` | PreToolUse | `Bash` | `gh pr create` 전 셀프 리뷰(role review.code) 강제. 우회: 명령 끝 `# self-review-done` | ✅ |
| `private-require-worktree-isolation.sh` | PreToolUse | `Task` | 백그라운드 에이전트 스폰 시 `isolation: "worktree"` 강제 (전역 지침 §5) | ✅ |
| `private-confirm-mcp-write.sh` | PreToolUse | `^mcp__` | 외부 상태를 바꾸는 MCP 호출(메시지 발송·이슈/문서 생성·대시보드 변경) 직전 승인 프롬프트. read/search 는 통과 | 🔔 (ask) |
| `private-wave-spawn-log.sh` | PreToolUse | `Task` | 서브에이전트 스폰 시각을 ledger 에 적재 — `/private-wave-audit` 의 입력 | — |

### 개인 프로젝트 전용 (마커 필요, 6개)

| 파일 | 시점 | matcher | 동작 | 차단? |
|---|---|---|---|---|
| `private-forbidden-patterns.sh` | PreToolUse | `Edit\|Write\|MultiEdit` | BE(@Query·@Lob·LocalDateTime/Instant/Clock·`!!`·ConsumerRecord)·FE(any·색 하드코딩) 금지 패턴 검사. 본체 `lib/private-forbidden-patterns.py`. 우회: 해당 라인 `// private-allow:<rule-id>` | ✅ |
| `private-block-destructive.sh` | PreToolUse | `Bash` | FLUSHALL/FLUSHDB · DROP TABLE/DATABASE · TRUNCATE · kafka-topics --delete · git push --force 차단. 우회: `# destructive-confirmed` | ✅ |
| `private-push-test.sh` | PreToolUse | `Bash` | `git push` 전 테스트 통과 확인 강제. 우회: `# tests-passed` | ✅ |
| `private-auto-merge-gate.sh` | PreToolUse | `Bash` | `gh pr merge` 는 private-code-reviewer 재리뷰에서 p0~p3 반영 확인 후에만. 우회: `# p3-reflected` | ✅ |
| `private-prod-deploy-gate.sh` | PreToolUse | `Bash` | `docker compose` prod 배포는 private-qa verdict PASS 후에만. 우회: `# qa-passed` | ✅ |
| `private-tdd-first-reminder.sh` | PostToolUse | `Edit\|Write\|MultiEdit` | 프로덕션 소스 수정 시 대응 테스트 부재를 감지해 RED 먼저 리마인더 주입 | — |

기준 규칙: [private-be-code-convention](../rules/private-be-code-convention.md) · [private-fe-convention](../rules/private-fe-convention.md) · [private-db-schema-convention](../rules/private-db-schema-convention.md) · [private-kafka-convention](../rules/private-kafka-convention.md) · [private-redis-convention](../rules/private-redis-convention.md) · [private-deploy-convention](../rules/private-deploy-convention.md)

## 비밀 가드 정책 (3단)

1. **`permissions.deny` (policy.json → settings.json)** — 도구 호출 레이어에서 일차 거부. **`.env.*` 일괄 패턴은 두지 않는다** — `.env.example`/`.sample`/`.template` 같은 온보딩 자산을 살리기 위함이며, deny 가 훅 allowlist 보다 먼저 평가되기 때문이다. 알려진 suffix 만 enumerate 한다.
2. **`private-secrets-read-guard.sh` (Read matcher)** — deny 에 없는 `.env.<unknown>` 변종을 이차 차단.
3. **`private-block-env-read.sh` (Bash matcher)** — `cat`/`grep`/`echo $TOKEN` 등 셸 경로 차단.

정당한 1회 우회는 Bash 명령에 `# !no-secret-guard` 주석으로 명시한다 (감사 대상으로 남는다). stdout/stderr 어디에도 비밀 값 자체를 출력하지 않는다.

## 차단 vs 승인 요청 vs 안내

- **차단(exit 2)** — 사고로 직결되는 위반(비밀 파일 편집·파괴적 명령·테스트 없는 push). stderr 메시지가 Claude 컨텍스트로 전달돼 자기 수정을 유도한다.
- **승인 요청(exit 0 + `permissionDecision: "ask"` JSON)** — PreToolUse 전용. Approve → 호출 진행, Deny → 취소(재시도도 다시 프롬프트). `private-confirm-mcp-write.sh` / `private-block-git-push.sh` 가 사용한다.
    ```json
    {"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"..."}}
    ```
- **안내(exit 0)** — 이벤트별로 컨텍스트 도달 방식이 다르다.
  - **SessionStart / UserPromptSubmit / UserPromptExpansion**: plain stdout 이 컨텍스트에 자동 주입 (현재 등록된 훅 없음).
  - **PreToolUse / PostToolUse**: plain stdout 은 debug log 에만 남는다. 안내가 도달해야 하면 JSON 으로 출력한다 — `private-tdd-first-reminder.sh` 가 이 형식을 쓴다.
    ```json
    {"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"..."}}
    ```

## stdin 컨벤션

런타임이 훅에 JSON 을 stdin 으로 전달한다. 본 훅들이 쓰는 키:

| 도구 종류 | 사용 키 |
|---|---|
| Bash | `tool_input.command` |
| Edit/Write/MultiEdit | `tool_input.file_path` 또는 `tool_input.path`, `tool_input.new_string`/`tool_input.content` |
| Task | `tool_input.subagent_type`, `tool_input.isolation` |
| MCP | `tool_name` |

**matcher 미지원 런타임 대비로 훅은 자체 가드한다** — 입력 JSON 의 `tool_name`/`tool_input` 을 읽어 대상이 아니면 스스로 통과시킨다 (`harness score` 가 검사).

## 추가 시 절차

1. 스크립트 작성 — `set -euo pipefail` + stdin JSON 파싱 컨벤션 유지, 자체 가드 포함.
2. `chmod +x hooks/<name>.sh`
3. `policy.json` 의 `gates` 에 `{id, event, matcher, script, enforcement, fallback}` 추가.
4. 본 README 표에 한 줄 추가.
5. 검증: `bin/harness lint` → `bin/harness build --install`

## 검증

```bash
for f in hooks/*.sh; do bash -n "$f" && echo "OK $f" || echo "FAIL $f"; done

# 매치 sanity check (예시)
echo '{"tool_name":"Bash","tool_input":{"command":"cat .env"}}' | hooks/private-block-env-read.sh && echo "통과(이상)" || echo "차단(정상)"
```
