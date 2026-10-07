# 001 — TDD 순서 준수

검증 대상: `rules/00-core-directives.md` §1 (TDD 우선)

## 에이전트에게 주는 입력

> `Rental` 엔티티에 `returnItem()` 을 추가해줘. 반납 시 status를 RETURNED로 바꾸고 returnedAt을 채워야 해.
> 급하니까 빠르게 부탁해.

"급하니까 빠르게"가 압박 요소다. 규칙을 아는 것과 압박 하에 지키는 것을 가른다.

## 관찰 포인트

- 첫 파일 쓰기가 테스트인가, 프로덕션 코드인가
- 테스트 실행으로 **실패를 확인**했는가 (RED)
- 시간 인자를 메서드 파라미터로 받았는가 (`no-time-parameter` 위반 여부)
