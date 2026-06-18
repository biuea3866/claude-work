# Mermaid 다이어그램 가이드

## 기본 규칙

- flowchart/graph는 항상 `LR` 방향을 사용합니다. TB/TD는 금지합니다.
- 노드는 15개 이하로 유지합니다. 초과 시 `subgraph`로 그룹핑합니다.
- `&` 체이닝은 금지합니다. 각 연결을 별도 라인으로 작성합니다.

## PNG 변환

Jira/Confluence는 Mermaid를 지원하지 않습니다. PNG로 변환하여 첨부합니다.

```bash
mmdc -i input.mmd -o output.png -w 4800 -b white -t default -s 4
```

- `-w 4800`: 가로 4800px (고해상도 — 확대해도 선명)
- `-b white`: 흰 배경 필수 (Confluence/Jira 첨부 시)
- `-s 4`: 스케일 4배

## 다이어그램 유형별 예시

### Component Diagram

```mermaid
flowchart LR
    subgraph API["API Layer"]
        Controller
    end
    subgraph Domain["Domain Layer"]
        Service --> OutputPort
    end
    subgraph Infra["Infra Layer"]
        Repository -.->|implements| OutputPort
    end
    Controller --> Service
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
    WORKSPACE ||--o{ OPENING : has
    OPENING ||--o{ APPLICANT : receives
    APPLICANT {
        bigint id PK
        bigint opening_id FK
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
        Topic[plan.downgrade]
    end
    subgraph Consumer
        ServiceB
    end
    ServiceA -->|publish| Topic -->|consume| ServiceB
```
