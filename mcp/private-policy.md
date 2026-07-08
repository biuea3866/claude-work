# [개인] MCP 정책 — 현재 서버 없음 (CLI로 충분)

개인 프로젝트(마커 `.claude/private-project` 레포)의 MCP 방침. 2026-07-02 결정.

## 결정

**개인 프로젝트에는 MCP 서버를 등록하지 않는다.** 파이프라인(agents/private-*)이 필요로 하는 외부 접근은 전부 CLI로 커버되고, MCP를 얹으면 인증 관리·세션 노이즈만 늘어난다.

| 필요 작업 | 담당 에이전트 | CLI 커버 |
|---|---|---|
| MySQL 스키마·데이터 확인 | private-mysql-implementer, private-senior-dba | `mysql` / `docker exec <컨테이너> mysql` |
| 마이그레이션 검증 | private-mysql-implementer | 로컬 MySQL 8.0 `docker run` + flyway |
| Redis 키·TTL 검증 | private-redis-implementer | `redis-cli` (`TTL`, `SET NX PX` 재현) |
| Kafka 토픽·계약 검증 | private-kafka-implementer | `kafka-topics`, `kafka-console-producer/consumer` |
| PR 생성·자동머지 | private-code-reviewer | `gh pr create` / `gh pr merge` (hook 게이트: `# p3-reflected`) |
| 라이브러리 문서 조회 | 전체 | context7 플러그인 MCP (이미 전역 로드됨 — 별도 등록 불필요) |
| 웹 조사 (벤치마킹·경쟁사) | private-prd-writer, private-senior-be/fe | WebSearch / WebFetch 내장 도구 |

## 나중에 MCP가 필요해지면

- **user scope(~/.claude.json)에 등록하지 않는다** — 회사 세션까지 로드된다.
- 필요한 개인 레포에만 `.mcp.json`을 만들어 커밋한다 (project scope) — [private-mcp-template.json](./private-mcp-template.json)을 복사해 필요한 서버 블록만 남기고 사용.
- 시크릿은 `.mcp.json`에 직접 넣지 않고 `${ENV_VAR}` 참조로 두고, 값은 셸 환경에서 주입한다.
- 이 파일의 표에 "왜 MCP로 승격했는지" 사유를 함께 갱신한다.

## 회사 MCP와의 관계

- 회사 레퍼런스(`atlassian.json`, `datadog.json`, `github.json`, `grafana.json`)와 무관 — 개인 프로젝트에서 Jira·Datadog·Grafana는 사용하지 않는다.
- claude.ai 커넥터(Atlassian·Slack 등)는 세션 전역이라 개인 프로젝트 세션에도 보이지만, private 에이전트들은 해당 도구를 참조하지 않는다.
