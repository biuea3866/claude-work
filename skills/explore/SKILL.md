---
name: explore
description: 기능/도메인/API/클래스명으로 관련 레포·파일·클래스를 빠르게 찾는다. .architecture/ 스냅샷을 우선 참조하고 필요 시 자동 재생성.
model: opus
user-invocable: true
---

탐색 대상: $ARGUMENTS

스냅샷: !`ls .architecture/ 2>/dev/null | wc -l | tr -d ' '`개 레포 보유

---

**탐색 접근 순서**
1. 아래 도메인 매핑 테이블로 후보 레포 결정
2. `.architecture/<repo>/api-map.md`, `domain-map.md` 읽기 (없으면 `bin/sync-architecture.sh --no-fetch <repo>`)
3. 스냅샷에서 파일 좁힌 후 실제 코드 진입
4. 레이어 순서로 추적: Controller → Facade → Service → Entity ← Repository

> 대형 `domain-map.md`는 grep 필터 후 읽기:
> `grep -n "<키워드>" .architecture/<repo>/domain-map.md | grep -i "facade\|service\|port" | head -40`

---

## 도메인 → 레포 매핑

프로젝트별 실제 레포 목록은 `.architecture/` 디렉토리 또는 레포 루트의 `CLAUDE.md`를 참조합니다.
아래는 일반적인 BE/FE 레이어 구분 예시입니다.

### BE — 핵심 도메인

| 도메인/기능 | 레포 | 비고 |
|------------|------|------|
| (프로젝트의 도메인 서비스) | `{be-repo}` | Hexagonal 4-레이어 |

### BE — 인프라

| 도메인/기능 | 레포 | 비고 |
|------------|------|------|
| DB 스키마 | `{db-schema-repo}` | Flyway 마이그레이션 |
| Kafka 토픽 | `{kafka-topic-repo}` | Terraform |

### FE

| 도메인/기능 | 레포 | 비고 |
|------------|------|------|
| (프로젝트의 FE 레포) | `{fe-repo}` | |
