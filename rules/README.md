# rules — 공통 가이드

모든 파이프라인/에이전트/스킬이 공통으로 참조하는 규칙 문서. Skill의 하위 레이어로, "문체/다이어그램/티켓/동기화" 같은 횡단 관심사를 한 곳에서 관리한다.

## 가이드 목록

| 파일 | 범위 | 누가 참조 |
|---|---|---|
| [output-style.md](./output-style.md) | 문체, 약어, 용어, 코드 참조 형식 | 모든 에이전트 산출물 |
| [mermaid.md](./mermaid.md) | Component/Sequence/ERD/Kafka 다이어그램 규칙, PNG 변환 | project-analyst, refactor-planner |
| [ticket-guide.md](./ticket-guide.md) | 티켓 md 구조, 사이즈 정의, 의존성 표기 | ticket-splitter |
| [jira-sync.md](./jira-sync.md) | md ↔ Jira 접두사 컨벤션, 의존성 연결 규칙 (실행은 `jira-ticket` skill) | ticket-splitter |
| [tdd-template.md](./tdd-template.md) | Technical Design Document 섹션 구조 | project-analyst, refactor-planner |
| [document-sync.md](./document-sync.md) | TDD 동기화 원칙 및 주의사항 (실행은 `doc-sync` skill) | impl-doc-sync, pipeline-runner |
| [be-code-convention.md](./be-code-convention.md) | Kotlin/Spring BE 컨벤션 (Hexagonal + Rich Domain) | be-implementer, be-senior, be-tech-lead, pr-reviewer |
| [pr-guide.md](./pr-guide.md) | 브랜치 네이밍, PR 제목/본문 템플릿, Hook 강제 (실행은 `pr-create` skill) | be-implementer, fe-implementer, code-reviewer |

## 참조 방식

에이전트/스킬 본문에 아래처럼 링크만 명시:

```markdown
## 사용 공통 가이드
- [output-style](rules/output-style.md) — 모든 산출물 문체
- [mermaid](rules/mermaid.md) — 다이어그램 3종
- [ticket-guide](rules/ticket-guide.md) — 티켓 분해 시
```

→ 에이전트 실행 시 Claude가 해당 파일을 로드해 규칙 적용.

## 수정 원칙

- **단일 진실 원천**: 문체/용어/규칙은 여기에만 작성. Agent/Skill에 중복 복붙 금지.
- **변경 시 전파**: common 파일이 바뀌면 참조 에이전트/스킬 모두 자동 적용됨 (링크만 유지하면 됨).
- **프로젝트별 오버라이드**: 프로젝트 특화 규칙은 CLAUDE.md에 덧붙이기.
