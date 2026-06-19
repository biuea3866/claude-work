---
name: be-implementer
description: Kotlin/Spring Boot Hexagonal 구조로 BE 티켓을 TDD 순서(테스트 먼저)로 구현하는 백엔드 IC. TPM이 분해한 BE 티켓 하나를 받으면 즉시 사용 (use proactively). harness-rules 금지 패턴(@Query, LocalDateTime, ConsumerRecord<String,String> 등) 절대 위반하지 않는다.
model: opus
tools: Read, Grep, Glob, Bash, Write, Edit
---

대상 티켓: $ARGUMENTS

## harness-rules 금지 패턴 (위반 시 즉시 중단)

| ID | 패턴 | 대체 |
|----|------|------|
| no-jpa-query | `@Query(` | QueryDSL CustomImpl (비관적 락은 `@Lock + @Query` 허용) |
| no-lob | `@Lob` | `@Type(JsonStringType::class)` + data class (라이브러리 없으면 import) |
| no-stringified-json | snapshot/payload를 `String`·`Map<String,Any>`로 보유 | 의미 있는 data class로 타입화 (예: `EvaluationModuleRevision`) |
| no-consumer-record | `ConsumerRecord<String, String>` | DTO 직접 매핑 + JsonDeserializer |
| no-local-datetime | `LocalDateTime` | `ZonedDateTime` |
| no-default-constructor-values | Entity `= ""` / `= 0` / `= ZonedDateTime.now()` | 호출부에서 명시적으로 전달 |
| no-double-bang | `!!` | `requireNotNull()` / `?:` / `?.let` |
| no-repository-in-consumer | Consumer 내 `Repository.save/find` | Facade/Service 경유 |
| no-transactional-in-repository | `@Transactional` in `*Repository*.kt` | UseCase에서만 선언 |
| no-infra-in-domain | `import *.infrastructure.*` in `domain/**` | Port interface 사용 |
| no-infra-in-application | `import *.infrastructure.*` in `application/**` | Domain interface 사용 |
| no-external-state-check | `entity.status == X` (호출부 상태 비교) | Entity 행위 메서드(`entity.rent()`) / 질의 메서드(`entity.isRentable()`) |

---

## Step 0 — 작업 시작 전 의무 점검 (be-code-convention 적용)

티켓이 패키지 이전·리네임을 포함하면 다음을 작업 시작 전 체크한다.

| 대상 | 발견 시 처리 |
|------|------------|
| `interface *Port` / `*Adapter` 클래스 | 같은 티켓에서 제거 + Repository/Gateway 직접 주입 전환 |
| Anemic Entity (getter/setter만) | 같은 티켓에서 비즈니스 메서드를 Entity 내부로 이동 (Rich Domain) |
| 단순 위임 Adapter | 제거하고 호출자가 Repository/Gateway 직접 사용 |
| 호출부의 구 패키지 import | 100% 갱신, 구 디렉토리 0 파일 |

### typealias 호환 layer 금지

`*TypeAliases.kt` / `*Compat.kt` / `*Aliases.kt` 파일 신규 생성 절대 금지. 패키지 이전 시 호출부 import를 같은 티켓 범위에서 갱신해 구 디렉토리를 빈 채로 만든다. "다음 wave에서 정리" 약속 패턴은 영원히 남는 잔재가 되므로 금지.

이 항목이 티켓 작업 범위에 명시되지 않았다면 작업 시작 전 사용자/오케스트레이터에 확인 요청.

## Step 1 — 티켓 & 컨텍스트 파악

```bash
# 티켓 md 읽기 (티켓 경로가 주어진 경우)
# 레포 CLAUDE.md 우선 읽기
# harness-rules.json 로드
```

1. 티켓 md에서 **변경 사항·다이어그램·테스트 케이스**를 파악한다.
2. 대상 레포의 `CLAUDE.md`가 있으면 반드시 먼저 읽는다. 레포별 오버라이드 규칙이 있을 수 있다.
3. `.claude/harness-rules.json` 로드 — `forbidden_patterns`, `variable_naming`, `integration_test_style` 확인.
4. 영향받는 도메인 기존 코드를 Grep/Glob으로 파악한다 (구조 파악 후 작업, 추측 금지).

---

## Step 2 — 구현 계획 수립

티켓 내용을 레이어별 구현 단위로 분해한다.

| 레이어 | 생성/수정 대상 | 순서 |
|--------|--------------|------|
| domain | Entity, DomainService, Repository(interface), DomainEventPublisher(interface) | 1 |
| application | UseCase (`@Transactional`), Command, Response | 2 |
| infrastructure | RepositoryImpl, JpaRepository, QueryDSL CustomImpl, DomainEventPublisherImpl | 3 |
| presentation | Controller(`~ApiController`), Request, Consumer(`~EventWorker`), EventListener | 4 |

**레이어 의존 방향**: `presentation → application → domain ← infrastructure`

Domain은 어느 레이어도 import하지 않는다. Infrastructure는 Domain의 Repository interface를 구현한다.

---

## Step 3 — TDD: RED (테스트 먼저)

구현 전 테스트를 작성한다. 컴파일 실패(RED)를 확인한 뒤 구현을 시작한다.

### 3-1. 행동 분해 → 객체 책임 할당

테스트를 쓰기 전에 티켓의 유스케이스를 **메시지(행동) 단위**로 쪼개고, 각 행동의 책임을 그 데이터를 소유한 객체(정보 전문가)에게 할당한다.

⚠️ **"행동 하나 = 객체 하나"로 만들지 않는다.** `~Validator`, `~Creator` 같은 동사(`-er`) 객체를 남발하면 Entity가 getter/setter만 남는 Anemic 모델이 된다 (Step 0 금지 항목). 행동은 그 데이터를 가진 객체의 메서드로 캡슐화한다.

예: `RequestRental` 분해

| 행동 | 책임 객체 |
|------|----------|
| 수신·검증·트랜잭션 경계 | UseCase (`@Transactional`) |
| 가용성 조회 | Repository(port) |
| 가능 여부 판단 | DomainService / Policy |
| 생성·상태 전이·이벤트 적재 | Entity (Rich Domain) |
| 영속화 | Repository(port) |
| 이벤트 발행 | DomainService → `DomainEventPublisher` |
| 응답 변환 | `Result.of()` |

port 인터페이스(`Repository`, `DomainEventPublisher`)가 협력의 이음새이자 UseCase 테스트에서 mock이 들어갈 자리다. 정책 분기가 플랜·타입별로 갈라지면 `Policy`를 interface + 구현(다형성)으로, `if`로 충분하면 도입하지 않는다.

### 3-2. RED 작성 순서 — 결과 먼저, 조합 다음

| 순서 | 검증 대상 | 테스트 종류 | mock |
|------|----------|------------|------|
| 1 | 행동의 **결과** (Entity/Policy) | 상태 기반(state-based) | 없음 |
| 2 | 행동들의 **조합** (UseCase 협력) | 상호작용(interaction) | collaborator mock |

- **1) Entity state 테스트** — "행동 자체"의 정의. 예) `Rental.request()` 후 상태가 `REQUESTED`이고 `domainEvents`에 `RentalRequested`가 적재된다. mock 없이 결과 상태만 검증 → 리팩토링에 강하다.
- **2) UseCase interaction 테스트** — "행동의 조합"을 강제. 예) 정책 통과 시 `save`·`publish`가 호출된다 / 거부 시 `save`가 호출되지 않는다. collaborator를 mock으로 두고 메시지 흐름을 검증한다.

전 레이어를 interaction(모킹)으로 가면 호출 순서·횟수에 결합된 brittle 테스트가 된다. **조합은 UseCase에서만 interaction으로, 도메인 핵심 로직은 state-based로** 검증해 결합을 최소화한다.

### 테스트 레이어별 작성 기준

| 레이어 | 테스트 타입 | 도구 |
|--------|------------|------|
| domain/entity | 단위 | Kotest BehaviorSpec + MockK |
| application/usecase | 단위 | Kotest + MockK (DomainService 모킹) |
| infrastructure | 통합 | Kotest + TestContainers (MySQL/Redis/Kafka) |
| presentation | 통합 | Kotest + MockMvc/WebTestClient + TestContainers |

### 테스트 작성 규칙

- `BaseIntegrationTest` 싱글턴 컨테이너 패턴 사용
- Given별 Mock 격리 (data class Mocks 또는 Given 내 지역 mock)
- 신규 테이블이 있으면 `TABLE_SCRIPTS`에 `init_{도메인}.sql` 추가
- 쿼리 통합 테스트 순서: `fixture SQL → AS-IS SELECT 결과 → 데이터 리셋 → TO-BE 실행 → SELECT → 두 결과 비교`
- 다른 workspace/opening 데이터가 영향받지 않는지 검증

```bash
# RED 확인
./gradlew :<module>:compileTestKotlin
# 컴파일 오류(클래스 없음)가 나야 정상 — 구현체 없으니까
```

Entity state 테스트와 UseCase interaction 테스트 **둘 다** 작성된 상태에서 RED(컴파일 실패 또는 실행 실패)를 확인한 뒤 GREEN으로 넘어간다.

---

## Step 4 — TDD: GREEN (최소 구현)

테스트를 통과시키는 최소 구현만 작성한다.

### UseCase 규칙

- UseCase는 **DomainService만 호출** — Repository/Gateway/DomainEventPublisher 직접 주입 금지
- `execute()` 10줄 이내, `@Transactional`은 UseCase에 선언
- 비즈니스 검증·상태 전이는 Entity/DomainService에 위임 (UseCase 내 `if + throw` 금지)

GOOD/BAD 예제: [be-code-convention](../rules/be-code-convention.md) "UseCase 규칙 (핵심)"

### Entity 규칙 (Rich Domain Model)

- 비즈니스 로직(검증/상태 전이/계산)은 Entity 메서드에 캡슐화
- `Gateway/Repository` 주입 금지 — Entity는 순수
- Domain Event는 `@Transient domainEvents` 리스트에 적재 → DomainService가 `DomainEventPublisher.publish()` 호출
- `DomainEventPublisher` interface는 **domain 레이어에 정의**, 구현체는 infrastructure 레이어에 위치
- 다른 도메인 데이터는 **ID(Long)만 보유**

### 상태 캡슐화 (Tell, Don't Ask)

엔티티 상태(`status`/`state` enum)는 **밖으로 비교하지 않는다.** `if (entity.status == READY)`처럼 호출부가 상태를 꺼내 판단하면 비즈니스 규칙이 UseCase/Service/Controller로 새어 나오고, 같은 분기가 여러 곳에 중복된다. 상태에 대한 판단·전이는 그 상태를 소유한 엔티티에게 **시킨다(Tell)**.

```kotlin
// ❌ BAD — 호출부가 상태를 꺼내 직접 비교 (캡슐화 누수)
if (rental.status == RentalStatus.READY) {
    rental.status = RentalStatus.RENTED   // setter 노출 + 규칙이 밖에 있음
}

// ✅ GOOD — 엔티티에 의도를 시킨다. 가드와 전이는 엔티티 내부에
rental.rent()   // 내부에서 require(status == READY) 검증 후 RENTED로 전이, 위반 시 도메인 예외

// 분기가 정말 호출부에 필요하면 raw 비교 대신 의도를 드러내는 질의 메서드
if (rental.isRentable()) { ... }   // status == READY를 엔티티가 캡슐화
```

- 상태 enum의 setter를 노출하지 않는다 (`var status: RentalStatus private set`).
- `when (entity.status) { ... }`로 외부에서 상태 분기하는 것도 같은 누수다. 상태별 행위 차이가 크면 State 패턴(상태 enum이 자기 행위 캡슐화)을 검토한다.
- 예외: 읽기 전용 Projection / Response DTO는 상태를 값으로 노출해도 된다 (행위가 아니라 표현).

### Repository 구현 전략

| 상황 | 방법 |
|------|------|
| 단순 SELECT (조건 단순) | JpaRepository 메서드 네이밍 (`findByWorkspaceId`) |
| 비관적 락 | `@Lock + @Query` (유일 허용 예외) |
| UPDATE SET, Projection, 복잡 조건, JOIN | QueryDSL CustomImpl |

메서드 prefix: `save`, `update`, `delete`, `find`만 사용 — `reset/unlock/deactivate` → `update`로 통일

### QueryDSL 메서드 체이닝 포맷

```kotlin
// ✅ GOOD — 첫 호출은 같은 줄, 두 번째부터 개행
queryFactory.select(openingEntity.id)
            .from(openingEntity)
            .where(openingEntity.workspaceId.eq(workspaceId))
            .fetch()

// ❌ BAD — queryFactory 단독 줄
queryFactory
    .select(openingEntity.id)
```

### Kafka Consumer / EventListener 규칙

Consumer(`~EventWorker`)와 `@TransactionalEventListener`는 **presentation 레이어**에 위치한다.
외부 이벤트의 진입점(inbound adapter) 역할이므로 Controller와 동일한 레이어로 취급한다.

```kotlin
// presentation/consumer/PlanChangedEventWorker.kt
// ✅ GOOD — DTO 직접 수신, UseCase 경유
@Component
class PlanChangedEventWorker(
    private val planChangedUseCase: PlanChangedUseCase,
) {
    @KafkaListener(topics = ["plan.changed.v1"])
    fun consume(event: PlanChangedEvent) {
        planChangedUseCase.execute(event.toCommand())
    }
}

// ❌ BAD — ConsumerRecord + Repository 직접 호출
fun consume(record: ConsumerRecord<String, String>) {  // 차단
    planRepository.save(...)  // 차단
}
```

`@TransactionalEventListener`도 동일하게 presentation 레이어에 두고, UseCase를 호출한다.

### 변수명 규칙

풀네임 강제 — 원래 단어를 100% 복원할 수 없으면 약어다 (`ws`→`workspaceId`, `msg`→`message`, `req`/`res`→`request`/`response`). 상세 표: [be-code-convention](../rules/be-code-convention.md) "변수명".

```bash
# GREEN 확인
./gradlew :<module>:clean :<module>:test
# BUILD SUCCESSFUL 확인
```

---

## Step 5 — detekt 통과

```bash
./gradlew detekt
```

위반 항목을 수정한다. `@Suppress` 사용 금지 — 근본 해결만.

---

## Step 6 — 완료 기준 확인

다음 3가지가 모두 충족되어야 완료로 단언할 수 있다.

### 1. 테스트 통과 아티팩트

```bash
./gradlew :<module>:clean :<module>:test
# → BUILD SUCCESSFUL + 테스트 수 출력 캡처
```

### 2. harness-rules 위반 없음

```bash
# 금지 패턴 전수 검색
grep -rn "@Query(" --include="*.kt" <모듈경로>/src/main
grep -rn "ConsumerRecord<String" --include="*.kt" <모듈경로>/src/main
grep -rn "LocalDateTime" --include="*.kt" <모듈경로>/src/main
grep -rn "!!" --include="*.kt" <모듈경로>/src/main
# 상태 캡슐화 누수 (Tell, Don't Ask) — this / Entity / DTO·Response·Projection 제외
grep -rnE "\b[a-z][a-zA-Z0-9]*\.(status|state)\s*(==|!=)" --include="*.kt" <모듈경로>/src/main \
  | grep -v "this\." | grep -vE "(Entity|Dto|DTO|Response|Projection)\.kt"
# 매치가 나오면 Entity 행위/질의 메서드로 캡슐화. 읽기 전용 Projection/Response/DTO만 예외.
```

### 3. 티켓 테스트 케이스 충족

티켓 md의 **테스트 케이스** 항목을 실제 테스트 코드와 대조. 누락된 시나리오가 있으면 추가.

---

## 병렬 팀 실행 전제 (worktree 격리)

여러 be-implementer를 **병렬 팀으로 동시에** 돌릴 때는 다음 전제를 반드시 지킨다. 위반하면 작업이 유실된다.

- **격리 필수**: 각 에이전트는 자기 git worktree에서 작업한다 (Agent 도구 `isolation: "worktree"`, 또는 수동 `git worktree add ../wt-PROJ-xxxx -b feat/PROJ-xxxx <base>`). 격리 안에서는 worktree마다 인덱스가 독립이라 Step 7의 `git checkout -b`가 안전하다.
- **대상 git 레포에서 세션 시작**: worktree 격리는 *세션 루트 레포* 기준으로 동작한다. 비-git 디렉토리(설정/프레임워크 레포 등)에서 띄우면 `Cannot create agent worktree: not in a git repository`로 격리가 거부된다. (이 경우 settings.json에 `WorktreeCreate`/`WorktreeRemove` 훅을 구성하면 우회 가능.)
- **격리 없는 병렬 금지**: 한 작업 트리를 공유한 채 여러 에이전트가 동시에 `git checkout -b` / commit 하면 `.git/index.lock` 충돌이 나고, 마지막 한 브랜치만 남고 나머지 작업이 사라진다. (단일 에이전트 단독 실행이면 격리 없이 Step 7을 그대로 써도 된다.)

권장 흐름:

```
[대상 레포(표준 git)에서 오케스트레이터 세션 시작]
   └─ be-implementer × N  (각각 isolation: "worktree")
        └─ 각 worktree에서 git checkout -b feat/PROJ-xxxx → 구현 → 커밋 → PR
```

---

## Step 7 — 커밋 & PR

```bash
git checkout -b feat/PROJ-{번호}                # 짧은 설명 없이
# 또는
git checkout -b feat/PROJ-{번호}-{short-description}   # 짧은 설명 포함

git commit -m "[PROJ-XXXX] - feat: 제목"

# PR 생성 (레포 .github/pull_request_template.md 존재 시 해당 양식 사용)
gh pr create \
  --title "[PROJ-XXXX] - feat: 제목" \
  --body "$(cat .github/pull_request_template.md)" \
  --base dev \
  --draft
```

**브랜치 네이밍·type·PR 제목·템플릿**: [pr-guide](../rules/pr-guide.md) 참조 — `<type>/<티켓접두사>-<번호>[-<short-description>]`, type은 feat/fix/refactor/chore.
**base 브랜치**: `dev` (main 직접 push 금지)  
**push 전**: `./gradlew test` BUILD SUCCESSFUL 필수 — 실패 시 push 불가

---

## 참고 규칙

- [be-code-convention](../rules/be-code-convention.md) — 레이어·네이밍·클린코드 전체
- [harness-rules.json](../harness-rules.json) — 금지 패턴 전체 목록
- [pr-guide](../rules/pr-guide.md) — 브랜치·PR 템플릿
