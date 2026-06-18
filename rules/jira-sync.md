# Jira 동기화 가이드

## 원칙

md 티켓 파일이 Source of Truth입니다. Jira는 md를 반영하는 뷰입니다.

→ 이슈 생성/수정/렌더링 검토는 `jira-ticket` 스킬을 사용합니다.

## Summary 접두사 컨벤션

| 담당 | 접두사 |
|------|--------|
| BE | `[BE]` |
| FE | `[FE]` |
| DB 스키마 | `[DB]` |
| Kafka/Infra | `[INFRA]` |
| plan-data-processor | `[plan-worker]` |

## 의존성 연결 규칙

`A is blocked by B` — A가 B에 의존할 때 사용.

의존 범위(`A-03~A-09`)는 각각 개별 링크로 생성합니다 (bulk API 없음).
