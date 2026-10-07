<!-- 생성 파일 — 직접 수정하지 마세요. -->
<!-- SSOT: /Users/biuea/.harness/rules/00-core-directives.md -->
<!-- 재생성: /Users/biuea/.harness/bin/harness build --install -->

> 이 세션의 작업 하네스 SSOT는 `/Users/biuea/.harness` 입니다.
> 세션 시작 시 [/Users/biuea/.harness/HARNESS.md](/Users/biuea/.harness/HARNESS.md) 의 **진입 절차**를 따르세요.

# 전역 작업 지침 (Core Directives)

모든 프로젝트·모든 런타임에 적용되는 최상위 행동 규칙. 레포 로컬 `.harness`/`CLAUDE.md`와 충돌하면 **로컬을 우선**한다. 단 §1 TDD 와 §2 완료 단언은 로컬이 명시적으로 면제하지 않는 한 항상 적용한다.

## 1. TDD 우선 — 코드 구현의 기본 흐름 (위반 금지)

코드를 작성·수정할 때는 **항상 테스트를 먼저 작성**한다. 구현부터 쓰지 않는다. 서브에이전트뿐 아니라 **메인 에이전트가 직접 구현할 때도 동일**하다.

- **RED** — 요구사항을 검증하는 실패하는 테스트를 먼저 작성하고, 실행해 실패를 확인한다.
- **GREEN** — 테스트를 통과시키는 최소 구현을 작성한다.
- **REFACTOR** — 테스트가 통과하는 상태에서 정리한다.

규칙:

- 프로덕션 코드 한 줄을 쓰기 전에, 그 코드를 강제하는 **실패하는 테스트가 먼저 존재**해야 한다.
- "구현부터 하고 테스트는 나중에" 는 금지다. 그렇게 진행 중임을 깨달으면 **즉시 멈추고** 테스트-퍼스트로 되돌린다.
- 테스트 프레임워크·레이어 범위는 레포 컨벤션을 따른다 (Kotlin/Spring → Kotest, 전 레이어 domain/application/infrastructure/presentation/scenario).
- 규모 있는 BE 구현은 `implement.be` role에 위임한다 — 이 role이 TDD 순서를 강제한다. 메인에서 직접 구현할 때도 위 순서를 그대로 지킨다.
- 신규 기능·다중 레포는 `/private-feature`, 가벼운 작업은 `/private-implement` 파이프라인을 우선 검토한다 (둘 다 TDD 강제 구현 단계를 포함).

상세 기준: [private-be-code-convention](./rules/private-be-code-convention.md) "필수 테스트 레이어", [private-tdd-review-criteria](./rules/private-tdd-review-criteria.md).

## 2. 완료 단언 규칙

"완료 / 통과 / 검증 끝" 같은 단언은 [COMPLETION-RULE](./rules/COMPLETION-RULE.md) §1~4 를 모두 충족해야 한다.

- 검증 아티팩트(테스트 raw 출력·빌드 로그·CI 링크 등)를 **단언과 같은 메시지에** 첨부한다.
- 도구 호출이 **단언 텍스트보다 먼저** transcript 에 있어야 한다. "했습니다" 라고 쓰기 전에 실제로 실행한다.
- 빌드·테스트 결과는 **exit code 로 확인**한다. `... | tail` 같은 파이프는 끝 명령의 exit code 만 남겨 실패를 가린다 — `BUILD SUCCESSFUL`/`FAILED` 문자열을 직접 확인하거나 `set -o pipefail` 을 쓴다.
- 충족 못 한 항목이 하나라도 있으면 항상 `in-progress` 로 보고한다.
- **`exec_shell` 능력이 없는 런타임**(L0)에서는 검증을 실행할 수 없다. 이때 "통과"를 단언하지 않고, 실행해야 할 명령을 제시한 뒤 결과를 입력받는다 ([capabilities](/Users/biuea/.harness/capabilities.md#강등-사다리)).

## 3. 공통 규칙 로드 (SSOT)

작업 시작 시 `~/.harness/rules/` 의 관련 가이드를 로드해 적용한다 — 코드 컨벤션·리뷰 기준·문체·다이어그램·티켓·DB 스키마. 단일 진실 원천은 `rules/` 이며, 그 내용을 다른 문서에 복제하지 않는다.

- **전량 로드 금지** — 필요한 규칙만 ID로 선택 로드한다. 컨텍스트 예산은 저가·소형 모델 노드에서 곧바로 병목이 된다.
- 문체·용어·코드 참조 형식: [output-style](./rules/output-style.md)
- 코드 리뷰 등급·체크: [private-code-review-criteria](./rules/private-code-review-criteria.md)
- 전체 목록: [rules/README](./rules/README.md)

## 4. 구현 전 사고

- 가정하지 않는다. 모호하면 멈추고 질문한다.
- 해석의 여지가 여럿이면 임의 선택하지 말고 대안을 제시한다.
- 더 단순한 방법이 있으면 제안하고, 정당한 사유가 있으면 사용자 요청에 반대 의견을 낸다.
- 필요한 부분만 정밀하게 수정한다 (무관한 리팩토링·포맷 변경 금지).

## 5. 워크트리 격리 (Worktree Isolation) — 동시 세션 안전

코드 작성·수정·테스트·커밋은 **항상 격리된 git worktree에서 수행**한다. 메인 worktree에서 직접 브랜치를 만들거나 커밋하지 않는다.

- 작업 시작 시 전용 worktree를 만들고(`git worktree add`), 그 안에서만 브랜치·편집·테스트·커밋한다.
- **이유**: 같은 레포에 동시 세션이 있을 수 있다. 메인 worktree는 공유 HEAD·인덱스·working tree를 가지므로, 직접 작업하면 다른 세션이 브랜치를 전환하거나 더티 파일을 남겨 ① 커밋이 엉뚱한 브랜치에 얹히고 ② pre-push 훅이 무관한 모듈 테스트로 행에 걸리는 사고가 난다 (실제 발생 이력 있음).
- **메인 worktree는 건드리지 않는다** — 다른 세션의 미커밋 변경을 `reset`/`checkout`/`stash`로 날리지 않는다. 메인이 점유 중이면 격리 worktree에서 작업하고, 머지는 서버사이드(GitHub Git Data API)로 처리한다.
- 배포(launchd 재구동 등)처럼 메인 worktree 경로를 읽어야 하는 작업은 동시 세션이 메인을 비운 뒤 수행한다.

## 6. 하네스 SSOT

- 하네스 정의(규칙·페르소나·스킬·정책)의 원본은 **`~/.harness`** 다.
- `~/.claude/settings.json`·`~/.claude/CLAUDE.md`·`~/.codex/config.toml` 등은 **생성물**이다. 직접 고치지 않는다 — `policy.json`을 고치고 `bin/harness build`를 돌린다.
- 상세: [HARNESS.md](/Users/biuea/.harness/HARNESS.md) "SSOT 규칙"
