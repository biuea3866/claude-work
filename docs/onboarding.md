# 온보딩 — 새 머신에서 하네스 복원

목표: **clone → 링크 → 빌드 → 진단**까지 5분. 이 문서만 보고 끝나야 한다.

## 0. 전제

| 항목 | 확인 |
|---|---|
| Python 3 | `python3 --version` (표준 라이브러리만 쓴다 — 추가 설치 없음) |
| git | `git --version` |
| Claude Code | `claude --version` |
| Codex CLI (교차 리뷰용) | `codex --version` · `codex login status` |

Codex가 없으면 그대로 진행해도 된다 — 3단계에서 `claude-only` 프로파일로 전환하면 전 단계가 claude로 돈다.

## 1. clone

```bash
git clone <이 저장소> ~/.harness
cd ~/.harness
```

경로는 `~/.harness` 고정이다. 스킬·어댑터가 이 경로를 참조한다.

## 2. 링크 + 빌드

```bash
bin/harness link            # 드라이런 — 무엇이 바뀌는지 먼저 본다
bin/harness link --install  # ~/.claude/{rules,agents,skills,commands,hooks,mcp} → ~/.harness 심링크
bin/harness build --install # policy.json → ~/.claude/settings.json · CLAUDE.md 생성
```

- 기존 `~/.claude/agents` 등이 실디렉토리면 `*.pre-harness`로 백업한 뒤 링크한다. 덮어쓰지 않는다.
- `settings.json`은 **병합**이다 — Orca 등 외부 도구가 주입한 훅은 보존된다.

## 3. 시크릿·프로파일

```bash
cp secrets.local.example.json secrets.local.json   # 있으면. 없으면 아래 형식으로 직접 생성
```

```json
{ "PLAYWRIGHT_MCP_EXTENSION_TOKEN": "<실제 값>" }
```

`policy.json`은 `${secrets.KEY}`로만 참조하고, 실값은 이 파일에 둔다 (gitignore 대상). 값이 없으면 빌드가 그 env를 **생략하고 경고**한다 — 빈 값으로 넣지 않는다.

Codex를 안 쓸 거면 `roles.json`의 `active_profile`을 `claude-only`로 바꾸고:

```bash
bin/harness graph --sync && bin/harness lint
```

## 4. 진단

```bash
bin/harness doctor   # 런타임 능력·심링크·생성물 드리프트
bin/harness lint     # 정의 정합성 (exit 1 = 오류)
bin/harness score    # 품질 Rubric (합격선 90)
```

셋 다 통과하면 준비 완료다.

## 5. 첫 실행

개인 프로젝트 레포에 마커가 있어야 개인 파이프라인이 열린다.

```bash
cd <레포> && touch .claude/private-project && git add .claude/private-project
claude
```

```
/private-feature <요구사항>     # PRD→설계→구현→리뷰 (사용자 게이트 2회)
/private-implement <요구사항>   # 설계 없이 바로 구현→리뷰
/private-review                 # 현재 브랜치 리뷰
```

## 자주 막히는 곳

| 증상 | 원인·조치 |
|---|---|
| 슬래시 커맨드가 안 보임 | 링크 미적용 — `bin/harness link --install` 후 세션 재시작 |
| 훅이 안 걸림 | `bin/harness build --install` 누락 또는 `~/.claude/settings.json` 드리프트 (`doctor`가 알려준다) |
| `codex exec` 실패 | `codex login status` 확인. 모델 id는 `bin/harness role <role>`의 `invoke`가 정본 |
| 개인 스킬이 "마커 없음"으로 중단 | 해당 레포에 `.claude/private-project` 생성 |
| `run status`가 엉뚱한 run을 가리킴 | `runs/`의 최신 run이 기본값이다. `--run <run-id>`로 지정 |

## 참고

- [HARNESS.md](../HARNESS.md) — 진입 절차·우선순위·변경 절차
- [ssot-map.md](./ssot-map.md) — 무엇을 어디서 고치나
- [capabilities.md](../capabilities.md) — 런타임 능력·강등
