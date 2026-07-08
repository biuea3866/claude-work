# [개인] FE 코드 컨벤션 (React / React Native)

개인 프로젝트용 FE 컨벤션 — React(웹) + React Native(앱). `private-fe-implementer`, `private-senior-fe`, `private-code-reviewer`가 공통 참조한다 (SSOT).

## 금지 패턴 (위반 시 즉시 중단 — private-code-reviewer p1)

| ID | 패턴 | 대체 |
|----|------|------|
| no-any | `any` 타입 | `unknown` + 타입 좁히기, 제네릭 |
| no-loose-assertion | 타입 단언(`as`) 남용 (검증 없는 외부 데이터 단언 포함) | 스키마 검증(zod 등) 후 좁히기, 타입 가드 |
| no-direct-fetch | 컴포넌트에서 `fetch`/`axios` 직접 호출 | `api/` 클라이언트 + query 훅 경유 |
| no-hardcoded-color | 색 하드코딩 (`#fff`, `rgb(...)`, Tailwind 원색 클래스 직접 사용) | 시맨틱 토큰 (라이트/다크 모드 위반) |
| no-single-mode | 한 모드(라이트만/다크만)로 구현된 화면 | 두 모드 모두 구현해야 완료 |
| no-global-by-default | 지역 상태·서버 상태를 전역 스토어에 배치 | 서버 상태는 Query, 지역은 useState — 정말 전역인 것만 Zustand |
| no-logic-in-component | 컴포넌트 내부의 비즈니스 로직·데이터 가공 | 훅·유틸로 추출 |
| no-abbrev | 변수명 축약 (`msg`, `cfg`, `res`, `btn`) | 풀네임 |
| no-junit-style-snapshot | 동작 검증 대용 snapshot 테스트 | 사용자 관점 동작 테스트 (Testing Library) |

## 표준 스택

| 관심사 | 표준 | 비고 |
|---|---|---|
| 서버 상태 | TanStack Query | 캐싱·재요청·낙관적 업데이트는 Query 기능 사용 |
| 전역 클라이언트 상태 | Zustand | "정말 전역"인 것만 (테마·세션 등). 스토어 비대화 금지 |
| 지역 상태 | `useState` / `useReducer` | 기본값 — 전역 승격은 근거 필요 |
| 스타일 (웹) | Tailwind CSS | 토큰은 CSS 변수로 정의, Tailwind 설정이 변수를 참조 |
| 스타일 (RN) | StyleSheet + 테마 훅 | `useTheme()` 훅이 토큰 객체 반환 |
| 테스트 | Testing Library (+ 레포의 러너: Vitest/Jest) | 웹 `@testing-library/react`, RN `@testing-library/react-native` |
| 언어 | TypeScript strict | `strict: true` 전제 |

레포에 이미 다른 라이브러리가 정착돼 있으면 레포 관례를 따르고, 신규 도입만 이 표를 기준으로 한다.

## 테마 토큰 · 다크 모드 (의무)

- 모든 색은 **시맨틱 토큰**(`background`, `surface`, `text-primary`, `text-secondary`, `border`, `accent`, `danger` 등)으로만 사용한다. 토큰 정의는 설계 문서의 토큰 → 라이트/다크 매핑 표가 SSOT.
- 웹: 토큰을 CSS 변수로 선언하고 `.dark` 클래스(또는 `data-theme`)로 전환. Tailwind 설정은 CSS 변수를 참조 (`colors: { background: 'var(--background)' }`).
- RN: 토큰 객체(light/dark)를 정의하고 `useTheme()` 훅으로 소비. `useColorScheme()` 기본 + 사용자 오버라이드 허용.
- **두 모드 모두 구현·확인해야 화면 완료.** 한 모드만 스타일된 컴포넌트는 리뷰 반려 대상.

## 디자인 기준 — 토스(Toss) 벤치마킹

- 화면 구성·컴포넌트·인터랙션은 토스 패턴을 기준으로 한다: 단순한 위계, 한 화면 한 과업, 명확한 단일 CTA, 절제된 색 사용(accent는 화면당 한 곳), 충분한 여백.
- 설계 문서에 화면별 참고 토스 패턴을 명시하고, 구현은 설계의 와이어프레임을 따른다.

## 아키텍처

### 폴더 구조 (레이어 기반)

```
src/
  components/   # 재사용 UI 컴포넌트 (도메인 무관)
  screens/      # (RN) 화면 단위  |  pages/ (웹) 페이지 단위
  hooks/        # 커스텀 훅 (비즈니스 로직·query 훅)
  api/          # API 클라이언트 + 엔드포인트 함수 + 요청/응답 타입
  stores/       # Zustand 스토어
  types/        # 공용 타입 (API 스키마 포함)
  utils/        # 순수 유틸리티
  theme/        # 토큰 정의·테마 훅
```

### 계층 규칙

- **API 호출 흐름**: 컴포넌트 → query 훅(`hooks/`) → 엔드포인트 함수(`api/`) → 클라이언트. 컴포넌트가 `api/`를 직접 import하지 않는다.
- **컴포넌트는 렌더링에 집중** — 데이터 가공·분기 로직은 훅·유틸로. 한 컴포넌트 200줄 초과 시 분리 검토.
- API 응답은 `types/`의 스키마 타입으로 정의 — BE 설계 문서의 API 계약과 필드·타입이 일치해야 한다.

### 웹/RN 공유 경계

- 공유 대상: 타입·API 클라이언트·훅(로직)·유틸·토큰 정의
- 공유하지 않는 것: 컴포넌트(플랫폼별 작성) — 공유 강제 금지
- RN 플랫폼 분기는 `Platform.select` / `.ios.tsx`·`.android.tsx`로 명시

## 상태·데이터 규칙

- 서버 데이터를 Zustand/useState에 복사 보관 금지 — Query 캐시가 SSOT
- 낙관적 업데이트·재시도는 필요한 인터랙션에만, 실패 롤백 흐름과 함께 구현
- 모든 데이터 화면은 4가지 상태(loading/empty/error/success)를 처리한다 — empty·error UI 누락은 미완성

## 접근성

- 웹: 시맨틱 태그, 인터랙티브 요소에 label, 키보드 조작 가능
- RN: 인터랙티브 요소에 `accessibilityLabel` + `accessibilityRole`

## 테스트 규칙 (TDD — 컴포넌트 단위까지)

- RED → GREEN → REFACTOR. 프로덕션 코드보다 실패하는 테스트가 먼저.
- 테스트는 **사용자 관점 동작** 검증 — 보이는 텍스트·role·인터랙션 결과. 구현 상세(내부 state·함수 호출)는 검증하지 않는다.
- 필수 커버: 컴포넌트(렌더링·인터랙션·실패 상태), 훅(`renderHook`), 유틸(단위). 케이스는 해피·실패·엣지 최소 3개.
- 완료 기준: 테스트 + `tsc --noEmit` + lint 전부 exit code 0.

## 참고 문서

- [private-tdd](./private-tdd.md) — 설계 문서 구조
- [private-ticket](./private-ticket.md) — 티켓 작성 규약
- [private-code-review-criteria](./private-code-review-criteria.md) — 리뷰 등급·verdict
