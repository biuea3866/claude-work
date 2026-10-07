---
id: mermaid
title: Mermaid 다이어그램 가이드
scope: task
level: MUST
context: common
paths:
  - "**/*.md"
  - "**/*.mmd"
---

# Mermaid 다이어그램 가이드

## 기본 규칙

- flowchart/graph는 항상 `LR` 방향을 사용합니다. TB/TD는 금지합니다.
- 노드는 15개 이하로 유지합니다. 초과 시 `subgraph`로 그룹핑합니다.
- `&` 체이닝은 금지합니다. 각 연결을 별도 라인으로 작성합니다.

## PNG 변환

Mermaid를 렌더링하지 못하는 곳에 붙일 때는 PNG로 변환합니다.

```bash
mmdc -i input.mmd -o output.png -w 4800 -b white -t default -s 4
```

- `-w 4800`: 가로 4800px (고해상도 — 확대해도 선명)
- `-b white`: 흰 배경 (문서 첨부 시 가독성)
- `-s 4`: 스케일 4배

## 다이어그램 유형별 예시

### Component Diagram

```mermaid
flowchart LR
    subgraph Presentation["Presentation"]
        Controller
    end
    subgraph Application["Application"]
        UseCase
    end
    subgraph Domain["Domain"]
        DomainService --> Repository
    end
    subgraph Infra["Infrastructure"]
        RepositoryImpl -.->|implements| Repository
    end
    Controller --> UseCase
    UseCase --> DomainService
```

### Sequence Diagram

```mermaid
sequenceDiagram
    participant C as Controller
    participant S as Service
    participant R as Repository
    C->>S: execute(command)
    S->>R: save(entity)
    R-->>S: entity
    S-->>C: result
```

### ERD

```mermaid
erDiagram
    USER ||--o{ ALERT : owns
    ALERT ||--o{ ALERT_HISTORY : records
    ALERT {
        bigint id PK
        bigint user_id FK
        varchar symbol
        varchar status
    }
```

### Kafka Event Flow

```mermaid
flowchart LR
    subgraph Producer
        ServiceA
    end
    subgraph Kafka
        Topic[alert.triggered]
    end
    subgraph Consumer
        ServiceB
    end
    ServiceA -->|publish| Topic -->|consume| ServiceB
```
