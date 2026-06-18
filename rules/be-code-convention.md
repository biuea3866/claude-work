# BE 코드 컨벤션 (Kotlin / Spring Boot)

Hexagonal Architecture + Rich Domain Model을 기반으로 하는 BE 실전 컨벤션. `be-implementer`, `be-senior`, `be-tech-lead`, `pr-reviewer`가 공통 참조한다.

## 레이어 책임

| 레이어 | 책임 | 허용 의존 | 금지 |
|---|---|---|---|
| **presentation** | 라우팅(Controller), 인증, Request→Command 변환, UseCase 호출, **Kafka Consumer/EventListener** (외부 이벤트 진입점) | application | 비즈니스 로직 |
| **application** | UseCase 단위 오케스트레이션 | domain | Repository/Gateway/DomainEventPublisher 직접 참조, 비즈니스 로직 |
| **domain** | 순수 비즈니스 로직 (Rich Domain Model), Repository·Gateway·DomainEventPublisher **interface 정의** | (없음) | Infrastructure 참조, 다른 도메인 패키지 import |
| **infrastructure** | Domain interface 구현체 (Repository/Gateway/DomainEventPublisher), 기술 어댑터 (DB·Kafka·외부 API) | domain | — |

> **OutputPort 패턴은 사용하지 않습니다.** Domain layer에는 Repository / Gateway / DomainEventPublisher interface를 직접 정의하고, infrastructure가 구현합니다.

## UseCase 규칙 (핵심)

### 원칙
1. UseCase 1개 = 행위 1개 = 클래스 1개
2. `execute()` 10줄 이내
3. `@Transactional`은 UseCase에 선언
4. **DomainService만 호출** — Repository/Gateway/EventPublisher 직접 참조 절대 금지
5. 비즈니스 로직(검증/상태전이/계산) 금지 — Entity/DomainService 위임

### 안티 패턴 (하네스가 차단)

```kotlin
// ❌ BAD — UseCase가 Repository 직접 호출 + if+throw 나열
class RequestRentalUseCase(
    private val productRepository: ProductRepository,  // 차단 no-repo-in-usecase
    private val rentalRepository: RentalRepository,
) {
    @Transactional
    fun execute(command: RequestRentalCommand): RequestRentalResult {
        val product = productRepository.findById(command.productId)
            ?: throw ResourceNotFoundException(...)
        if (product.isOwnedBy(command.renterId)) {  // 차단 no-if-throw-in-usecase
            throw BusinessException(...)
        }
        product.validateAvailableForRental()
        val rental = Rental.create(...)
        return RequestRentalResult.of(rentalRepository.save(rental))
    }
}
```

### 올바른 패턴

```kotlin
// ✅ GOOD — UseCase는 DomainService만 호출
class RequestRentalUseCase(
    private val rentalDomainService: RentalDomainService,
) {
    @Transactional
    fun execute(command: RequestRentalCommand): RequestRentalResult {
        val rental = rentalDomainService.requestRental(command)
        return RequestRentalResult.of(rental)
    }
}

// DomainService에서 조회 + 검증 + 실행
class RentalDomainService(
    private val rentalRepository: RentalRepository,
    private val productDomainService: ProductDomainService,
    private val eventPublisher: DomainEventPublisher,
) {
    fun requestRental(command: RequestRentalCommand): Rental {
        val product = productDomainService.getProductById(command.productId)
        product.validateNotOwnedBy(command.renterId)   // Entity 내부에서 throw
        product.validateAvailableForRental()
        val rental = Rental.create(command)
        return rentalRepository.save(rental).also {
            eventPublisher.publishAll(it.pullDomainEvents())
        }
    }
}

// Entity 내부 캡슐화 — Rich Domain Model
class Product(...) {
    fun validateNotOwnedBy(userId: Long) {
        if (isOwnedBy(userId)) throw SelfRentalException(...)
    }
    fun validateAvailableForRental() {
        if (!status.canRent()) throw NotRentableException(...)
    }
}
```

## Entity 규칙 (Rich Domain Model)

- 비즈니스 로직(검증/상태 전이/계산)은 Entity 메서드에 캡슐화
- Entity 내부에 `Repository / Gateway / DomainEventPublisher` 주입 금지 — Entity는 순수
- Anemic Domain Model(getter/setter만) 금지
- 상태 전이는 Enum 내부 `canTransitTo()`로 캡슐화
- Domain Event는 Entity 내부 `@Transient domainEvents` 리스트에 적재 → DomainService가 `DomainEventPublisher.publishAll()`로 발행
- 다른 도메인 데이터는 **ID(Long)만 보유** — Entity 객체 직접 참조 금지

## 레이어 의존 방향

```
presentation → application → domain ← infrastructure
```

- Domain은 어느 것도 import하지 않는다 (순수)
- Infrastructure는 Domain의 Repository / Gateway / DomainEventPublisher interface를 구현
- 도메인 패키지 간 참조 금지 (`domain.rental`에서 `domain.product` import 불가, `domain.common`만 허용)

## 네이밍 컨벤션

| 역할 | 위치 | 파일명 |
|---|---|---|
| Controller | presentation | `~ApiController.kt` |
| Kafka Consumer / EventListener | presentation | `~EventWorker.kt` |
| UseCase | application | `~UseCase.kt` |
| Entity | domain | 도메인명 (`Rental.kt`, `Product.kt`) |
| Domain Repository (DB 영속화) | domain | `~Repository.kt` (interface) |
| Domain Gateway (외부 시스템 호출: 외부 API/SMS/이메일) | domain | `~Gateway.kt` (interface) |
| Domain Event Publisher | domain | `DomainEventPublisher.kt` (interface) |
| JPA Repository | infrastructure | `~JpaRepository.kt` |
| Repository 구현 | infrastructure | `~RepositoryImpl.kt` |
| Gateway 구현 | infrastructure | `~GatewayImpl.kt` |
| Event Publisher 구현 | infrastructure | `KafkaDomainEventPublisher.kt` 등 |
| Command | application | `~Command.kt` |
| Request | presentation | `~Request.kt` |
| Response | application | `~Response.kt` |

**Repository vs Gateway 구분**:
- Repository → DB 영속화 (JPA, MyBatis, MongoDB 등)
- Gateway → 외부 시스템 호출 (외부 SaaS API, SMS, 이메일, 결제, 푸시 등)

### PK 네이밍
- 엔티티 PK는 `id`로 통일 (`user_id` X, `id` O)
- 참조 FK 컬럼은 `user_id`, `product_id` 사용

### 변수명
- 풀네임 강제 — `workspaceId` ✓, `ws` ✗
- 약어 금지: `comp` → `component`, `eval` → `evaluation`

## DTO 흐름

```
Request (presentation)
  → Command (application)
    → Entity (domain)
      → Response (application)
        → 그대로 presentation 반환
```

- Request: 외부 입력 형태
- Command: UseCase 실행 파라미터 (`toCommand()`로 변환)
- Response: UseCase 반환값, presentation이 그대로 사용

## 트랜잭션 & 이벤트

| 상황 | 위치 |
|---|---|
| 기본 트랜잭션 | UseCase `@Transactional` |
| Domain Event 발행 | DomainService가 `DomainEventPublisher` interface(domain layer)로 호출, 구현체는 infrastructure (Kafka·Spring ApplicationEventPublisher 등) |
| 이벤트 처리 | `@TransactionalEventListener(AFTER_COMMIT)` — **presentation layer**에 위치, UseCase 경유 |
| 도메인 간 이벤트 | 비동기 (`@Async` + `@Retryable`) |

## 클린 코드 규칙

- UseCase `execute()` 10줄 이내
- DomainService 메서드 15줄 이내
- 한 메서드는 하나의 추상화 수준만 (`entity.markPaid()`와 `repository.save()` 공존 금지)
- Guard clause(early return) 적극 사용
- if-else 중첩 depth 2 이상 금지
- 매직 넘버/문자열 금지 (상수/enum)
- 주석 대신 메서드명으로 의도 표현
- 한 메서드는 한 가지 일만

### Guard Clause 예시

```kotlin
// ❌ BAD
fun process(id: Long): Result {
    val entity = repository.find(id)
    if (entity != null) {
        if (entity.isValid()) {
            return entity.process()
        } else {
            throw InvalidException()
        }
    } else {
        throw NotFoundException()
    }
}

// ✅ GOOD
fun process(id: Long): Result {
    val entity = repository.find(id) ?: throw NotFoundException()
    if (!entity.isValid()) throw InvalidException()
    return entity.process()
}
```

## Null 안전

- `!!` 절대 금지 (하네스 차단)
- 대체: `requireNotNull`, `?:`, `?.let`
- nullable이 필요 없으면 `non-null`로 선언

## 생성자/함수 호출 포맷

| 조건 | 스타일 |
|---|---|
| 파라미터 5개 이하 + 타입 전부 다름 | namedArgument 없이 한 줄 |
| 파라미터 5개 이하 + 타입 중복 | namedArgument + 한 줄씩 개행 |
| 파라미터 5개 초과 | namedArgument + 한 줄씩 개행 |

## QueryDSL

- `@Query` 금지 (하네스 차단)
- CustomRepository interface + RepositoryImpl (QueryDSL) 패턴
- JpaRepository는 기본 CRUD만, 복잡 쿼리는 CustomRepositoryImpl에

## JSON 컬럼

- `@Type(JsonStringType::class)` + data class
- `ObjectMapper` 직접 사용 금지

## Kafka Consumer

- **위치**: presentation layer (`~EventWorker.kt`) — Controller와 동일한 외부 진입점
- `ConsumerRecord<String, String>` 금지 → DTO 직접 매핑
- `JsonDeserializer` + `trusted.packages` 설정
- Consumer에서 Repository / DomainService 직접 호출 금지 → **UseCase 경유**
- ObjectMapper 수동 파싱 금지

```kotlin
// presentation/consumer/PlanChangedEventWorker.kt
@Component
class PlanChangedEventWorker(
    private val planChangedUseCase: PlanChangedUseCase,
) {
    @KafkaListener(topics = ["plan.changed.v1"])
    fun consume(event: PlanChangedEvent) {
        planChangedUseCase.execute(event.toCommand())
    }
}
```

## 필수 테스트 레이어

모두 존재해야 PR 승인 가능. TDD(Test-Driven Development) 사이클(RED → GREEN → detekt)을 따른다.

| 레이어 | 대상 | 타입 | 도구 |
|---|---|---|---|
| domain | Entity, DomainService | 단위 | Kotest BehaviorSpec + MockK |
| application | UseCase | 단위 | Kotest + MockK (DomainService 모킹) |
| infrastructure | Repository·Gateway·DomainEventPublisher 구현 | 통합 | Kotest + TestContainers (MySQL/Redis/Kafka) |
| presentation | Controller, **EventWorker(Kafka Consumer), EventListener** | 통합 | Kotest + MockMvc/WebTestClient + TestContainers |
| scenario | E2E 비즈니스 플로우 | 시나리오 통합 | 가입→등록→대여→반납 등 전체 시나리오 |

## 티켓 사이즈

- S: ~200줄 (구현 코드 기준, 테스트 제외)
- M: ~400줄
- L: ~800줄 (초과 시 분할)

## 패키지 통합·이전 시 적용 원칙

패키지 리네임/통합은 **단순 디렉토리 이동이 아닌 아키텍처 정리 기회**다.

### 금지

- **typealias 호환 layer 신규 생성 금지** — `*TypeAliases.kt`, `*Compat.kt`, `*Aliases.kt` 파일을 새로 만들지 말 것. 호출부 import를 같은 티켓 범위에서 100% 갱신한다. "다음 wave에서 제거" 약속 패턴은 영원히 남는 잔재가 되므로 금지.
- **단순 디렉토리 이동만 하는 티켓 금지** — `git mv` + package 선언 변경만 하고 끝나면 안 된다.

### 필수

패키지 이전 티켓은 다음을 함께 수행한다:

1. **Port 인터페이스 발견 시 제거** — `interface *Port` / `class *Adapter` 패턴이 있으면 Repository/Gateway 직접 주입으로 전환.
2. **Adapter 패턴 잔재 → DomainService로 책임 흡수** — 단순 위임 Adapter는 제거.
3. **Anemic Domain Model → Rich Domain Model 재배치** — getter/setter만 있는 Entity는 비즈니스 메서드를 Entity 내부로 이동.
4. **Hexagonal layer 책임 재배치** — `domain` / `application` / `infrastructure` 책임을 명확히.
5. **호출부 import 100% 갱신** — 구 패키지 디렉토리는 티켓 완료 시점에 0 파일이어야 한다.

### 검증

```bash
# 구 패키지 디렉토리 잔재 0건
find <module>/src -path '*<old-package-path>*' -name '*.kt' | wc -l   # → 0

# Port 인터페이스 0건
grep -rn "interface .*Port" <module>/src/main --include="*.kt"        # → 0건

# typealias 호환 layer 0건
find <module>/src -name "*TypeAliases.kt" -o -name "*Compat.kt" -o -name "*Aliases.kt" | wc -l   # → 0
```

## 참고 문서
- [output-style](./output-style.md) — 문체/코드 참조 형식
- [tdd-template](./tdd-template.md) — 기술 설계 문서 템플릿
- [ticket-guide](./ticket-guide.md) — 티켓 작성 규약