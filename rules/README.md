# rules — 공통 가이드

모든 파이프라인·에이전트·스킬이 참조하는 규범. **검증 가능한 것만** 둔다 — "무엇을 어기면 반려인가"가 명확해야 한다.

## frontmatter 스키마 (필수)

```yaml
id: private-be-code-convention   # 파일명과 일치 (로드 순서 접두 `00-` 는 제외)
title: [개인] BE 코드 컨벤션
scope: always | task             # always = 세션마다 무조건 로드
level: MUST | SHOULD
context: common | private | company
paths:                            # (선택) 이 규칙이 적용되는 파일 glob
  - "**/*.kt"
```

## 선택 로드 (전량 로드 금지)

작업 대상 파일을 주면 적용 규칙만 나온다 — 컨텍스트 예산은 저가·소형 모델에서 곧바로 병목이 된다.

```bash
bin/harness rules src/main/kotlin/Rental.kt --context private
bin/harness rules --json          # 전체 인덱스
```

## 목록

| id | level | context | 적용 대상 | 제목 |
|---|---|---|---|---|
| [core-directives](./00-core-directives.md) | MUST | common | always | 전역 작업 지침 |
| [COMPLETION-RULE](./COMPLETION-RULE.md) | MUST | common | always | 완료 단언 규칙 (Completion Assertion Rule) |
| [mermaid](./mermaid.md) | MUST | common | `**/*.md`, `**/*.mmd` | Mermaid 다이어그램 가이드 |
| [output-style](./output-style.md) | MUST | common | always | 출력 스타일 가이드 |
| [private-be-architecture-rule](./private-be-architecture-rule.md) | MUST | private | `**/*.kt`, `**/*.kts` | [개인] BE 아키텍처 규칙 — 이벤트 기반 아키텍처 (Event-Driven Architecture) |
| [private-be-code-convention](./private-be-code-convention.md) | MUST | private | `**/*.kt`, `**/*.kts` | [개인] BE 코드 컨벤션 (Kotlin / Spring Boot) |
| [private-branch-convention](./private-branch-convention.md) | MUST | private | 절차 | [개인] 브랜치 전략 (trunk-based / origin/main 기준) |
| [private-code-review-criteria](./private-code-review-criteria.md) | MUST | private | 절차 | [개인] 코드 리뷰 기준 (p0~p5) |
| [private-db-schema-convention](./private-db-schema-convention.md) | MUST | private | `**/db/migration/*.sql`, `**/*.sql` | [개인] DB 스키마 컨벤션 (Flyway / MySQL 8.0) |
| [private-deploy-convention](./private-deploy-convention.md) | MUST | private | `**/docker-compose*.yml`, `**/docker-compose*.yaml` | [개인] 배포 컨벤션 (로컬 Docker — dev/prod 이원화) |
| [private-fe-convention](./private-fe-convention.md) | MUST | private | `**/*.tsx`, `**/*.ts`, `**/*.jsx`, `**/*.js` | [개인] FE 코드 컨벤션 (React / React Native) |
| [private-kafka-convention](./private-kafka-convention.md) | MUST | private | `**/docker-compose*.yml`, `**/docker-compose*.yaml`, `**/kafka/**` | [개인] Kafka 컨벤션 (로컬 docker compose / JSON 스키마) |
| [private-mongodb-convention](./private-mongodb-convention.md) | MUST | private | `**/mongo/migration/*.js` | [개인] MongoDB 컨벤션 |
| [private-pr-guide](./private-pr-guide.md) | MUST | private | 절차 | [개인] PR 작성 가이드 |
| [private-prd-template](./private-prd-template.md) | MUST | private | 절차 | [개인] PRD 템플릿 |
| [private-redis-convention](./private-redis-convention.md) | MUST | private | `**/docker-compose*.yml`, `**/docker-compose*.yaml`, `**/redis/**` | [개인] Redis 컨벤션 (캐시 / 락 / 랭킹·세션 / pub-sub) |
| [private-tdd-review-criteria](./private-tdd-review-criteria.md) | MUST | private | 절차 | [개인] 설계 문서(TDD) 검수 기준 |
| [private-tdd](./private-tdd.md) | MUST | private | 절차 | [개인] TDD(Technical Design Document) 템플릿 |
| [private-ticket](./private-ticket.md) | MUST | private | 절차 | [개인] 티켓 작성 가이드 |

## 수정 원칙

- **단일 진실 원천**: 규칙 본문을 agent·skill 에 복붙하지 않는다. 링크만 남긴다.
- **변경 시 전파**: 이 디렉토리를 고치면 참조하는 모든 에이전트에 즉시 적용된다.
- **프로젝트별 오버라이드**: 레포 특화 규칙은 그 레포 `CLAUDE.md` 에 덧붙인다.
- 이 목록은 `bin/harness lint` 가 실제 파일과 대조한다 — 파일을 추가하면 여기도 추가한다.
