# [개인] BE 코드 컨벤션 (Kotlin / Spring Boot)

개인 프로젝트용 BE 컨벤션 — Hexagonal Architecture + Rich Domain Model. `private-be-implementer`, `private-senior-be`, `private-code-reviewer`가 공통 참조한다 (SSOT). 회사 `be-code-convention.md`의 자급자족 복사본으로, 회사 rules 변경에 영향받지 않는다.

## 금지 패턴 (위반 시 즉시 중단 — private-code-reviewer p1)

개인 프로젝트에는 `harness-rules.json`이 없다. 이 표가 금지 패턴의 단일 기준이다.

| ID | 패턴 | 대체 |
|----|------|------|
| no-jpa-query | `@Query(` | QueryDSL CustomImpl (비관적 락은 `@Lock + @Query` 허용) |
| no-lob | `@Lob` | `@Type(JsonStringType::class)` + data class (라이브러리 없으면 의존성 추가) |
| no-stringified-json | snapshot/payload를 `String`·`Map<String,Any>`로 보유 | 의미 있는 data class로 타입화 |
| no-consumer-record | `ConsumerRecord<String, String>` | DTO 직접 매핑 + JsonDeserializer |
| no-local-datetime | `LocalDateTime` / `Instant` / `Clock` 타입 사용 | `ZonedDateTime`으로 통일 |
| no-clock-injection | 컴포넌트 빈에 `Clock` 주입 | Entity 캡슐화 메서드 내부에서 `ZonedDateTime.now()` 해결 |
| no-time-parameter | 도메인 캡슐화 메서드에 시간 인자 전달 (`returnItem(now)`) | 메서드 내부에서 시간 해결 (`returnItem()`) |
| no-default-constructor-values | Entity 생성자 `= ""` / `= 0` / `= ZonedDateTime.now()` | 호출부에서 명시적으로 전달 |
| no-double-bang | `!!` | `requireNotNull()` / `?:` / `?.let` |
| no-optional-return | `Optional<T>` 반환·보유 (`java.util.Optional`) | Kotlin nullable 타입 (`T?`) + `?:` / `?.let` |
| no-repository-in-consumer | Consumer 내 `Repository.save/find` | UseCase 경유 |
| no-transactional-in-repository | `@Transactional` in `*Repository*.kt` | UseCase에서만 선언 |
| no-infra-in-domain | `import *.infrastructure.*` in `domain/**` | Domain interface 사용 |
| no-infra-in-application | `import *.infrastructure.*` in `application/**` | Domain interface 사용 |
| no-external-state-check | `entity.status == X` (호출부 상태 비교) | Entity 행위 메서드(`entity.rent()`) / 질의 메서드(`entity.isRentable()`) |
| no-getter-chain-behavior | 래퍼/집계 객체의 내부를 꺼내 행위·검증 (`wrapper.inner.doX(..)`, `wrapper.inner.value` 비교) | 래퍼 자신의 캡슐화 메서드에 위임 (`wrapper.doX(..)`) |
| no-expose-value-for-external-logic | 객체 내부 값을 꺼내 외부 함수·검증에 전달 (`validate(obj.a, obj.b)`) | 그 판단 로직을 객체의 캡슐화 메서드로 (`obj.validate(..)`) |
| no-junit | 신규 테스트에 `org.junit.*` / `@Test` / SpringRunner | Kotest (BehaviorSpec/DescribeSpec/FunSpec) |
| no-conditional-on-property | 기능 on/off 분기에 `@ConditionalOnProperty` / `@Profile` (빈 등록 자체를 토글) | 피처 플래그 값을 런타임에 조회해 분기 ([피처 플래그](#피처-플래그-기능-토글)) |
| no-cross-context-reverse-dep | 공용 컨텍스트(payment·notification 등)가 주문/업무 컨텍스트(booking·goods·…) DomainService/Repository 역참조 — `OrderConfirmationGateway`류 `when(orderType)` 동기 디스패치 허브 | 공용 컨텍스트가 이벤트 발행 → 각 주문 컨텍스트가 자기 EventWorker로 확정 ([private-be-architecture-rule](./private-be-architecture-rule.md) "공용 컨텍스트 역참조 금지") |
| no-technical-item-name | 사용자 노출 문자열(PG 주문명 `itemName` 등)에 `"TYPE #id"`(`BOOKING #42`·`"$orderType #$orderId"`) 같은 기술 식별자 | 도메인의 사람이 읽는 이름(모집 제목·상품명·이벤트명 등). 이름은 그 주문 컨텍스트가 **자기 데이터로** 구성 (itemName 때문에 다른 컨텍스트 역참조 금지) |
| no-over-abstract-name | 도메인 의미가 없는 과도한 추상 네이밍 — 클래스·변수·메서드·테이블·컬럼에 `applications`·`event`·`suspend`·`data`·`info`·`item`·`type`·`status`·`process`·`handle` 같은 일반 명사 단독 사용 | 도메인 개념을 드러내는 이름 — `rentalApplications`/`membershipSuspension`/`RentalReturnedEvent`, 테이블 `rental_applications`, 컬럼 `suspended_reason`. "무엇의" 를 붙여 구체화 ([도메인 기반 네이밍](#도메인-기반-네이밍-과도한-추상화-금지)) |

## 레이어 책임

| 레이어 | 책임 | 허용 의존 | 금지 |
|---|---|---|---|
| **presentation** | 라우팅(Controller), 인증, Request→Command 변환, UseCase 호출, **Kafka Consumer/EventListener** (외부 이벤트 진입점) | application | 비즈니스 로직 |
| **application** | UseCase 단위 오케스트레이션 | domain | Repository/Gateway/DomainEventPublisher 직접 참조, 비즈니스 로직 |
| **domain** | 순수 비즈니스 로직 (Rich Domain Model), Repository·Gateway·DomainEventPublisher **interface 정의** | (없음) | Infrastructure 참조, 다른 도메인 패키지 import |
| **infrastructure** | Domain interface 구현체 (Repository/Gateway/DomainEventPublisher), 기술 어댑터 (DB·Kafka·외부 API) | domain | — |

> **OutputPort 패턴은 사용하지 않는다.** Domain layer에 Repository / Gateway / DomainEventPublisher interface를 직접 정의하고, infrastructure가 구현한다.

### 레이어 의존 방향

```
presentation → application → domain ← infrastructure
```

- Domain은 어느 것도 import하지 않는다 (순수)
- 도메인 패키지 간 참조 금지 (`domain.rental`에서 `domain.product` import 불가, `domain.common`만 허용)

## UseCase 규칙 (핵심)

1. UseCase 1개 = 행위 1개 = 클래스 1개
2. `execute()` 10줄 이내
3. `@Transactional`은 UseCase에 선언
4. **DomainService만 호출** — Repository/Gateway/EventPublisher 직접 참조 절대 금지
5. 비즈니스 로직(검증/상태전이/계산) 금지 — Entity/DomainService 위임. UseCase 내부 `if + throw` 비즈니스 검증 금지

```kotlin
// ❌ BAD — UseCase가 Repository 직접 호출 + if+throw 나열
class RequestRentalUseCase(
    private val productRepository: ProductRepository,      // 금지 no-repo-in-usecase
    private val rentalRepository: RentalRepository,
) {
    @Transactional
    fun execute(command: RequestRentalCommand): RequestRentalResult {
        val product = productRepository.findById(command.productId)
            ?: throw ResourceNotFoundException(...)
        if (product.isOwnedBy(command.renterId)) {          // 금지 no-if-throw-in-usecase
            throw BusinessException(...)
        }
        val rental = Rental.create(...)
        return RequestRentalResult.of(rentalRepository.save(rental))
    }
}

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
```

## Entity 규칙 (Rich Domain Model)

- 비즈니스 로직(검증/상태 전이/계산)은 Entity 메서드에 캡슐화
- Entity 내부에 `Repository / Gateway / DomainEventPublisher` 주입 금지 — Entity는 순수
- Anemic Domain Model(getter/setter만) 금지
- 상태 전이는 Enum 내부 `canTransitTo()`로 캡슐화
- Domain Event는 Entity 내부 `@Transient domainEvents` 리스트에 적재 → DomainService가 `DomainEventPublisher.publishAll()`로 발행
- 다른 도메인 데이터는 **ID(Long)만 보유** — Entity 객체 직접 참조 금지

### 캡슐화 위임 (Tell, Don't Ask / 디미터 법칙)

객체(Entity·래퍼·집계 DTO)의 **내부를 꺼내 호출부에서 처리하지 않는다.** 내부 구성요소에 대한 행위·검증은 그 객체가 **자기 메서드로 노출**해 위임받게 한다.

- **기차 충돌 금지**: `wrapper.inner.doSomething()`처럼 getter로 하위 객체를 꺼내 그 메서드를 호출하지 않는다. 래퍼가 `wrapper.doSomething()`을 노출한다.
- **내부 값 추출 후 외부 검증 금지**: `validate(obj.a, obj.b)`처럼 내부 값을 꺼내 외부 함수에 넘기지 않는다. 판단 로직을 `obj.validate(..)`로 객체 안에 둔다.
- 여러 구성요소를 묶은 집계 타입(`XxxWithYyy` 등)은 구성요소의 행위를 **자기 메서드로 재노출**한다 — 호출부는 구성요소 존재를 몰라야 한다.
- 이 규칙은 [no-getter-chain-behavior]·[no-expose-value-for-external-logic]로 강제되며, [no-external-state-check](호출부 상태 비교 금지)와 같은 원칙의 확장이다.

```kotlin
// ❌ BAD — 내부를 꺼내 호출부에서 처리 (기차 충돌 + 값 추출 후 외부 검증)
productWithStock.product.requireOwnedBy(ownerUserId)
validateQuantityWithinStock(productId, limitedQuantity, productWithStock.stockQuantity)

// ✅ GOOD — 래퍼가 캡슐화 메서드로 위임받는다
productWithStock.requireOwnedBy(ownerUserId)
productWithStock.validateQuantityWithin(limitedQuantity)

// ProductWithStock 내부
class ProductWithStock(private val product: Product, private val stockQuantity: Int) {
    fun requireOwnedBy(userId: Long) = product.requireOwnedBy(userId)
    fun validateQuantityWithin(requested: Int) {
        if (requested > stockQuantity) throw QuantityExceedsStockException(requested, stockQuantity)
    }
}
```

### Domain Entity와 JPA Entity 분리 시 — POJO 생성·필드 규칙

1. **생성자 `private`** — 정적 팩토리 메서드로만 생성: `create(command)`(신규, 검증 포함) / `reconstitute(...)`(영속화 복원, 무검증)
2. **생성자 파라미터 기본값 금지** — `= null`, `= 0`, `= ""` 금지. 초기값은 팩토리 메서드 내부에서 명시적으로.
3. **필드 `private var`** — `public var`도 `val`도 아님. 상태 변경은 의도가 드러나는 비즈니스 메서드로만. 읽기 노출은 `get()`-only 프로퍼티.

```kotlin
// ✅ GOOD
class Rental private constructor(
    private var status: RentalStatus,
    private var returnedAt: ZonedDateTime?,
) {
    val currentStatus: RentalStatus get() = status
    val isReturned: Boolean get() = returnedAt != null

    companion object {
        fun create(command: RequestRentalCommand): Rental {
            require(command.productId > 0) { "productId must be positive" }
            return Rental(status = RentalStatus.REQUESTED, returnedAt = null)
        }
        fun reconstitute(status: RentalStatus, returnedAt: ZonedDateTime?): Rental =
            Rental(status = status, returnedAt = returnedAt)
    }

    // 시간은 인자로 받지 않고 캡슐화 메서드 내부에서 해결한다
    fun returnItem() {
        status.validateCanReturn()
        this.status = RentalStatus.RETURNED
        this.returnedAt = ZonedDateTime.now()
    }
}
```

## 시간 타입 규칙

- 시간 타입은 **`ZonedDateTime`으로 통일** — `LocalDateTime`·`Instant`·`Clock` 사용 금지.
- **컴포넌트 빈에 `Clock` 주입 금지** — "테스트를 위한 Clock DI" 패턴을 쓰지 않는다.
- **도메인 캡슐화 메서드에 시간 인자를 넘기지 않는다** — `returnItem(now: ZonedDateTime)` ✗. 시간이 필요한 상태 전이는 메서드 내부에서 `ZonedDateTime.now()`로 해결한다 — `returnItem()` ✓.
- 시간 검증이 필요한 테스트는 결과 필드의 범위 검증(전후 시각 사이인지)으로 처리한다.

## 외부 API 호출 구조

- 외부 API 호출도 Repository와 동일하게 **domain interface + infrastructure 구현** 구조를 따른다: domain에 `~Gateway.kt` interface 정의 → infrastructure에 `~GatewayImpl.kt` 구현.
- HTTP 클라이언트(`XXXClient` — RestClient·WebClient·Feign 등)는 **GatewayImpl에만 DI**한다. domain·application 레이어에 Client 타입이 노출되면 안 된다.
- Client의 요청/응답 DTO는 infrastructure에 두고, GatewayImpl이 도메인 타입으로 변환해 반환한다.

```kotlin
// domain/payment/PaymentGateway.kt
interface PaymentGateway {
    fun charge(payment: Payment): PaymentResult
}

// infrastructure/payment/PaymentGatewayImpl.kt
@Component
class PaymentGatewayImpl(
    private val tossPaymentClient: TossPaymentClient,   // Client는 여기에만 DI
) : PaymentGateway {
    override fun charge(payment: Payment): PaymentResult =
        tossPaymentClient.requestPayment(payment.toClientRequest()).toDomain()
}
```

## 코틀린 함수형 프로그래밍 (적극 활용)

- 컬렉션 변환은 루프 대신 함수형 체인 — `map`/`filter`/`groupBy`/`fold`/`associateBy`. 단 한 체인이 3단계를 넘어 읽기 어려우면 중간 변수로 분리한다.
- 불변 우선 — `val` + 불변 컬렉션(`List`, `Map`)이 기본. `var`·`MutableList`는 지역 스코프에 한정.
- 스코프 함수를 의도에 맞게 — 변환 `let`, 부수 효과 `also`, 수신 객체 구성 `apply`. 남용으로 중첩되면 오히려 분리.
- `sealed class`/`sealed interface` + `when` 전수 분기 — else 브랜치 없이 컴파일러가 누락을 잡게 한다.
- null 처리는 함수형으로 — `?.let`, `?:`, `takeIf` (`!!` 금지는 상단 표와 동일).
- 고차 함수·함수 타입으로 중복 제거 — 동일 구조의 try-catch·트랜잭션 래핑 등.

## 객체지향·디자인 패턴 (적극 활용)

- **분기 대신 다형성** — 타입·상태별 if-else/when 분기가 2곳 이상 반복되면 sealed class·enum 메서드·전략 패턴으로 치환한다.
- 상황에 맞는 패턴을 명시적으로 채택하고 이름을 드러낸다:
  - 생성 — 정적 팩토리 메서드(`create`/`reconstitute`), 필요 시 빌더 대신 named argument
  - 행위 — 전략(정책 교체), 템플릿 메서드(공통 흐름 + 훅), 상태(상태 전이가 복잡할 때)
  - 구조 — 데코레이터(횡단 기능), 컴포지트(트리 구조)
- 패턴은 문제가 있을 때 도입한다 — 예상 확장을 위한 선제 추상화(스펙 없는 인터페이스 다중 구현)는 금지. "지금 두 번째 구현이 존재하는가"를 기준으로 한다.

## 네이밍 컨벤션

### 도메인 기반 네이밍 (과도한 추상화 금지)

클래스·객체·변수·메서드·DB 테이블·컬럼·이벤트·토픽 이름은 **그 도메인 개념을 드러내야** 한다. `applications`·`event`·`suspend`·`data`·`info`·`item`·`type`·`status`·`manager`·`process`·`handle` 같은 **일반 명사 단독**은 무엇을 다루는지 가리므로 금지한다 (no-over-abstract-name).

- **"무엇의" 를 붙여 구체화한다** — `applications` ✗ → `rentalApplications`·`membershipApplications` ✓ / `suspend()` ✗ → `suspendMembership()`·`suspendRental()` ✓ / `event` ✗ → `RentalReturnedEvent` ✓.
- **한 컨텍스트 안에서 자명하면 도메인명은 생략 가능하다** — `rental` 패키지 안의 Entity는 `Rental`, 그 안의 상태 컬럼은 `status`로 충분하다. 문제는 **경계를 넘어 의미가 모호해지는 이름**(공용 테이블 `applications`, 전역 `EventEntity`, 범용 `DataService`)이다.
- **판단 기준**: 이름만 보고 "무슨 도메인의 무엇인지" 답할 수 있으면 통과. `suspend` → "무엇을 정지?" 가 남으면 실패 → `suspendMembership`.
- 상태·타입 enum 값은 영문 유지하되 enum **타입명**에 도메인을 담는다 — `Status` ✗ → `RentalStatus` ✓, `Type` ✗ → `PaymentMethodType` ✓.
- DB 테이블·컬럼도 동일 — 상세는 [private-db-schema-convention](./private-db-schema-convention.md) "명명"·[private-mongodb-convention](./private-mongodb-convention.md) "명명".

| 역할 | 위치 | 파일명 |
|---|---|---|
| Controller | presentation | `~ApiController.kt` |
| Kafka Consumer / EventListener | presentation | `~EventWorker.kt` |
| UseCase | application | `~UseCase.kt` |
| Entity | domain | 도메인명 (`Rental.kt`) |
| Domain Repository (DB 영속화) | domain | `~Repository.kt` (interface) |
| Domain Gateway (외부 시스템 호출) | domain | `~Gateway.kt` (interface) |
| Domain Event Publisher | domain | `DomainEventPublisher.kt` (interface) |
| JPA Repository | infrastructure | `~JpaRepository.kt` |
| Repository 구현 | infrastructure | `~RepositoryImpl.kt` |
| Gateway 구현 | infrastructure | `~GatewayImpl.kt` |
| Event Publisher 구현 | infrastructure | `KafkaDomainEventPublisher.kt` 등 |
| Command | application | `~Command.kt` |
| Request | presentation | `~Request.kt` |
| Response | application | `~Response.kt` |

- **Repository vs Gateway**: Repository → DB 영속화 / Gateway → 외부 시스템 호출 (외부 API·SMS·이메일·결제·푸시)
- PK는 `id`로 통일, 참조 컬럼은 `user_id`, `product_id`
- 변수명 풀네임 강제 — `workspaceId` ✓, `ws` ✗. 약어 금지: `comp` → `component`

### 메서드 네이밍 — 동사 (+ 필요 시 전치사)

전치사는 의미를 더할 때만 붙이고, **전치사 뒤의 키·범위 이름은 생략**해 시그니처가 표현하게 한다.

| 전치사 | 의미 | 예 |
|---|---|---|
| `~By` | 조회·식별 키 | `findBy(userId)`, `deleteBy(scopeId)` |
| `~To` / `~From` | 변환 대상 / 출처로부터 생성 (짝) | `toResponse()` / `fromEntity(entity)` |
| `~With` | 동반 인자 | `mergeWith(other)` |
| `~In` | 범위·소속 | `findAllIn(scopeId)` |
| `~For` | 용도·대상 | `forMember(userId)` |

- 단순 동작은 전치사 없이 — `save(entity)`, `delete(id)`
- `findByScope(scopeType, scopeId)` → `findBy(scopeType, scopeId)`. 단 파라미터 타입만으로 구분이 안 되면 접미사 유지 — `forMember(userId: Long)` vs `forRole(roleId: Long)`
- **예외**: Spring Data JpaRepository 파생 쿼리는 프레임워크가 파싱하므로 `findByScopeTypeAndScopeId(...)` 유지. 중복 제거는 도메인 interface에만 적용
- 안티패턴: 의미 없는 전치사 부착(`saveBy`), 모호한 이름, `getXxx` 남용(조회 키가 있으면 `findBy~`)

### 팩토리 메서드 네이밍 (`of~` vs `for~` vs `from~`)

- `of~`: 인자 객체 자체로부터/집계로 생성 — `Result.of(entity)`
- `from~`: 단일 파라미터 타입 변환 — `fromEntity(entity)`
- `for~`: 특정 대상·용도를 위해 생성, 인자가 식별자일 때 — `forMember(userId)`. `ofMember(userId)`는 의미 불일치로 금지
- 그 외 표준 관례 (Effective Java Item 1): `valueOf` / `getInstance` / `newInstance`·`create` / `getType` / `newType`

## DTO 흐름

```
Request (presentation) → Command (application) → Entity (domain) → Response (application) → 그대로 presentation 반환
```

- Request: 외부 입력 형태 / Command: UseCase 실행 파라미터 (`toCommand()`로 변환) / Response: UseCase 반환값, presentation이 그대로 사용
- Controller가 Entity를 그대로 응답으로 반환 금지

## 트랜잭션 & 이벤트

| 상황 | 위치 |
|---|---|
| 기본 트랜잭션 | UseCase `@Transactional` |
| Domain Event 발행 | DomainService가 `DomainEventPublisher` interface(domain)로 호출, 구현체는 infrastructure |
| 이벤트 처리 (Layer 1) | `@TransactionalEventListener(AFTER_COMMIT)` — **presentation layer**, UseCase 경유 |
| 도메인 간 이벤트 (Layer 2) | Kafka 토픽 발행/구독 — 무관한 도메인, 비동기 |

> **이벤트를 언제 Spring ApplicationEvent(Layer 1)로, 언제 Kafka(Layer 2)로 나눌지** — 2단계 레이어 판단·발행/구독 구조는 [private-be-architecture-rule](./private-be-architecture-rule.md)이 SSOT다. 이 표는 코드 위치 규칙만 다룬다.

## 피처 플래그 (기능 토글)

기능의 on/off·점진 공개·A/B는 **피처 플래그 값을 런타임에 조회해 분기**한다. `@ConditionalOnProperty`·`@Profile`로 빈 등록 자체를 토글하지 않는다.

- **`@ConditionalOnProperty` / `@Profile` 금지 (no-conditional-on-property)** — 빈 존재 여부를 설정으로 가르면 ① 토글 변경에 재기동이 필요하고 ② 두 경로를 한 배포로 검증할 수 없으며 ③ 무중단 롤백(플래그 OFF)이 불가하다. 기능 분기는 코드 안에서 플래그를 조회해 처리한다.
- **레포에 피처 플래그 메커니즘이 이미 있으면 그것을 쓴다** — 새 토글 방식을 만들지 않는다. 기존 플래그 조회 지점을 찾아 동일한 방식으로 분기한다.
- **플래그 조회는 domain interface(Gateway) 뒤로 숨긴다** — DomainService가 `FeatureFlagGateway.isEnabled(flagKey)` 형태로 조회하고, 구현체(설정·외부 플래그 서비스·DB)는 infrastructure에 둔다. `@Value`·`Environment`를 domain/application에 직접 주입하지 않는다.
- **분기 결과는 Rich Domain으로** — 플래그 값을 꺼내 UseCase에서 `if + throw`로 나열하지 않는다. 플래그로 갈리는 정책은 Entity/DomainService의 캡슐화 메서드에 위임한다 (no-external-state-check와 동일 원칙).
- **양쪽 경로 모두 테스트** — 플래그 ON/OFF 두 케이스를 테스트로 강제한다. 플래그 조회를 Mock으로 주입해 분기별 동작을 검증한다.
- 플래그 제거 시점(기능 안정화 후 분기·플래그 삭제)을 설계 문서 Release Scenario에 함께 명시한다 — 영구 잔재 방지.

```kotlin
// ❌ BAD — @ConditionalOnProperty로 빈 자체를 토글 (재기동 필요, 무중단 롤백 불가)
@Component
@ConditionalOnProperty(name = ["rental.new-pricing.enabled"], havingValue = "true")
class NewPricingPolicy : PricingPolicy { ... }

// ✅ GOOD — 런타임 플래그 조회 + domain interface 뒤로 숨김
// domain/pricing/FeatureFlagGateway.kt
interface FeatureFlagGateway {
    fun isEnabled(flagKey: String): Boolean
}

// domain/pricing/PricingDomainService.kt
class PricingDomainService(
    private val featureFlagGateway: FeatureFlagGateway,
) {
    fun priceFor(rental: Rental): Money =
        rental.calculatePrice(useNewPricing = featureFlagGateway.isEnabled("rental.new-pricing"))
}
```

## 클린 코드 규칙

- UseCase `execute()` 10줄 이내 / DomainService 메서드 15줄 이내 / 단일 메서드 100줄 초과 금지
- 한 메서드는 하나의 추상화 수준만 (`entity.markPaid()`와 `repository.save()` 공존 금지)
- Guard clause(early return) 적극 사용, if-else 중첩 depth 2 이상 금지
- 매직 넘버/문자열 금지 (상수/enum), 주석 대신 메서드명으로 의도 표현

```kotlin
// ✅ Guard clause
fun process(id: Long): Result {
    val entity = repository.find(id) ?: throw NotFoundException()
    if (!entity.isValid()) throw InvalidException()
    return entity.process()
}
```

## 생성자/함수 호출 포맷

| 조건 | 스타일 |
|---|---|
| 파라미터 5개 이하 + 타입 전부 다름 | namedArgument 없이 한 줄 |
| 파라미터 5개 이하 + 타입 중복 | namedArgument + 한 줄씩 개행 |
| 파라미터 5개 초과 | namedArgument + 한 줄씩 개행 |

## QueryDSL

- `@Query` 금지 — CustomRepository interface + RepositoryImpl (QueryDSL) 패턴
- JpaRepository는 기본 CRUD만, 복잡 쿼리는 CustomRepositoryImpl에

## JSON 컬럼

- `@Lob` 금지 → `@Type(JsonStringType::class)` (hypersistence-utils, 없으면 의존성 추가)
- `ObjectMapper` 직접 사용 금지
- 구조 있는 데이터(snapshot·config·payload)를 raw `String`·`Map<String, Any>`로 보유 금지 → 도메인 의미를 담은 data class로 타입화 + `@Type(JsonStringType::class)` 매핑

## Kafka Consumer

- **위치**: presentation layer (`~EventWorker.kt`)
- `ConsumerRecord<String, String>` 금지 → DTO 직접 매핑, `JsonDeserializer` + `trusted.packages` 설정
- Consumer에서 Repository / DomainService 직접 호출 금지 → **UseCase 경유**

```kotlin
@Component
class PlanChangedEventWorker(
    private val planChangedUseCase: PlanChangedUseCase,
) {
    @KafkaListener(topics = ["event.plan.plan.v1"])   // plan 서브도메인, key=plan PK. changed는 payload 변이
    fun consume(event: PlanChangedEvent) {
        planChangedUseCase.execute(event.toCommand())
    }
}
```

## Null 안전

- `!!` 절대 금지 — `requireNotNull`, `?:`, `?.let`으로 대체
- **`Optional<T>` 반환 금지** — Java 관례 유입 차단. "없을 수 있음"은 Kotlin nullable(`T?`)로 표현한다. Repository 조회도 `fun findBy(id: Long): Rental?` — `Optional<Rental>` ✗. Spring Data가 `Optional`을 반환하는 파생 쿼리는 RepositoryImpl에서 `.orElse(null)` 등으로 즉시 풀어 도메인 interface 밖으로 새지 않게 한다.
- nullable이 필요 없으면 non-null로 선언

## 필수 테스트 레이어

> **테스트 프레임워크는 무조건 Kotest.** 신규 테스트에 JUnit 금지 — 전 레이어에서 Kotest(BehaviorSpec/DescribeSpec/FunSpec)로 작성한다. TDD 사이클(RED → GREEN → REFACTOR)을 따른다.

| 레이어 | 대상 | 타입 | 도구 |
|---|---|---|---|
| domain | Entity, DomainService | 단위 | Kotest BehaviorSpec + MockK |
| application | UseCase | 단위 | Kotest + MockK (DomainService 모킹) |
| infrastructure | Repository·Gateway·DomainEventPublisher 구현 | 통합 | Kotest + TestContainers (MySQL/Redis/Kafka) |
| presentation | Controller, EventWorker, EventListener | 통합 | Kotest + MockMvc/WebTestClient + TestContainers |
| scenario | E2E 비즈니스 플로우 | 시나리오 통합 | 전체 시나리오 (가입→등록→대여→반납 등) |

- 실 DB 없이 Mock만 작성한 통합 테스트는 테스트 누락과 동일하게 취급 (p2)

## 티켓 사이즈

- S: ~200줄 (구현 코드 기준, 테스트 제외) / M: ~400줄 / L: ~800줄 (초과 시 분할)

## 패키지 통합·이전 시 적용 원칙

패키지 리네임/통합은 아키텍처 정리 기회다.

### 금지
- **typealias 호환 layer 신규 생성 금지** — `*TypeAliases.kt`/`*Compat.kt`/`*Aliases.kt` 금지. 호출부 import를 같은 티켓에서 100% 갱신
- **단순 디렉토리 이동만 하는 티켓 금지**

### 필수
1. `interface *Port` / `*Adapter` 발견 시 제거 — Repository/Gateway 직접 주입 전환
2. 단순 위임 Adapter 제거 — DomainService로 책임 흡수
3. Anemic Entity → Rich Domain Model 재배치
4. 호출부 import 100% 갱신 — 구 디렉토리 0 파일

### 검증
```bash
find <module>/src -path '*<old-package-path>*' -name '*.kt' | wc -l          # → 0
grep -rn "interface .*Port" <module>/src/main --include="*.kt"               # → 0건
find <module>/src -name "*TypeAliases.kt" -o -name "*Compat.kt" | wc -l      # → 0
```

## 참고 문서

- [private-be-architecture-rule](./private-be-architecture-rule.md) — 이벤트 기반 아키텍처 (Layer 1 ApplicationEvent / Layer 2 Kafka 판단)
- [private-tdd](./private-tdd.md) — 기술 설계 문서 구조
- [private-ticket](./private-ticket.md) — 티켓 작성 규약
- [private-code-review-criteria](./private-code-review-criteria.md) — 리뷰 등급·verdict
