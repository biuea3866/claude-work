# ADR 0001 — 하네스를 `~/.harness` 단일 진실 원천으로 분리

- **날짜**: 2026-08-13
- **상태**: 채택
- **관련**: [HARNESS.md](../../HARNESS.md), [capabilities.md](../../capabilities.md)

## 배경

하네스 정의(규칙·페르소나·스킬·훅·권한)가 `~/.claude` 안에 있었다. `~/.claude`는 Claude Code의 **런타임 상태 디렉토리**이기도 해서 authored 콘텐츠와 세션·로그·크리덴셜이 한 곳에 섞여 있었다.

목표는 "어느 LLM 에이전트가 메인 세션 주도권을 가져가도 같은 하네스가 동작하는 것"인데, 정의가 특정 런타임 디렉토리에 있으면 그 목표가 구조적으로 불가능하다.

## 결정

authored 콘텐츠를 `~/.harness`로 분리하고 SSOT로 삼는다. 런타임 설정은 **생성물**로 강등한다.

| 대상 | 방식 | 근거 |
|---|---|---|
| `rules/` `agents/` `skills/` `commands/` `hooks/` `mcp/` | **심링크** | 포맷 호환. 드리프트 0, 빌드 불필요, `rm`+`mv` 한 번으로 롤백 |
| `settings.json` `config.toml` `hooks.json` `CLAUDE.md` `AGENTS.md` | **생성** | 런타임마다 스키마가 달라 중립 표현(`policy.json`)에서 컴파일해야 함 |

git 레포(`claude-work`)는 `~/.harness`로 이관해 168개 파일의 커밋 히스토리를 보존한다.

## 대안과 미채택 사유

| 대안 | 미채택 사유 |
|---|---|
| `~/.claude` 유지 + 다른 런타임에서 그 경로를 참조 | 이름부터 특정 런타임 종속. Codex 사용자가 `~/.claude`를 읽는 구조는 의미가 뒤집힌다 |
| 전부 생성(복사) 방식 — 심링크 없이 어댑터가 파일 복사 | `~/.claude/rules`에서 편집하면 다음 빌드에 소실된다. 실수 비용이 크고 이득이 없다 |
| 런타임별로 하네스를 따로 유지 | 규칙 중복 → 드리프트. SSOT 원칙 자체를 포기하는 선택 |

## 파급

- **좋아진 것**: 런타임 추가가 어댑터 하나 작성으로 끝난다. 규칙 변경이 모든 런타임에 즉시 전파된다.
- **비용**: 빌드 단계가 생긴다. `policy.json`을 고치고 `bin/harness build`를 돌리는 습관이 필요하다.
- **주의**: `settings.json`은 **공동 소유**다. Orca가 11개 이벤트에 자기 훅을 주입한다. 어댑터는 하네스 소유 항목(`$HOME/.claude/hooks/*.sh`)만 교체하고 나머지는 **병합 보존**해야 한다. 통째 덮어쓰면 Orca 연동이 끊긴다.

## 이관 시점 실측

- 추적 파일 168개 (skills 74 · hooks 29 · rules 27 · agents 25 · mcp 6 · commands 6 · .gitignore 1)
- 게이트 22개 — blocking 17 / advisory 5
- 외부(Orca) 주입 훅 11개 — 보존 대상
- 고아 훅 1개 발견: `custom-session-start.sh`가 `settings.json`에 미등록. 동작 검증 전까지 등록하지 않고 lint 경고로만 남긴다 (미검증 훅을 SessionStart에 붙이면 모든 세션이 영향을 받는다)
