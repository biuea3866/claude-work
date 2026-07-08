# [개인] 배포 컨벤션 (로컬 Docker — dev/prod 이원화)

개인 프로젝트의 배포 규칙. 배포 대상은 로컬 Docker이며, dev/prod를 compose 파일로 분리한다. `private-qa`·`private-senior-be`(Release Scenario)·hook `private-prod-deploy-gate.sh`가 공통 참조한다 (SSOT).

## 환경 구성

| 환경 | compose 파일 | 배포 명령 | 진입 조건 |
|---|---|---|---|
| dev | `docker-compose.yml` (기본) | `docker compose up -d --build` | `main` 머지 (숏텀 작업 브랜치 → main, [private-branch-convention](./private-branch-convention.md)) |
| prod | `docker-compose.prod.yml` | `docker compose -f docker-compose.prod.yml up -d` | **private-qa verdict PASS** |

- prod compose 파일명에는 반드시 `prod`가 들어간다 (`docker-compose.prod.yml` 표준) — hook이 이 규칙으로 prod 배포를 식별한다.
- compose profile을 쓰는 경우도 동일: `--profile prod`.

## prod 배포 게이트 (hook 강제)

1. `private-qa`를 실행해 **verdict PASS**를 받는다 (dev 실구동 E2E + 회귀 전체 통과, QA 리포트 저장).
2. PASS 확인 후 배포 명령 끝에 토큰을 붙인다:
   ```
   docker compose -f docker-compose.prod.yml up -d   # qa-passed
   ```
3. 토큰 없는 prod 배포는 hook(`private-prod-deploy-gate.sh`)이 차단한다. QA PASS 없이 토큰만 붙이는 것은 거짓 단언(COMPLETION-RULE 위반) — 감사 대상.

dev 배포는 게이트 없음 — 머지 전 파이프라인(리뷰어·push-test·auto-merge-gate)이 이미 방어한다.

## 이미지·롤백 규칙

- **prod 이미지 태그 = 릴리즈 태그 `{YYYYMMDD}-{NN}`** — 당일 시퀀스 2자리(zero-pad, `01`부터). `latest` 금지. git 태그와 docker 이미지 태그를 동일 값으로 고정하고 compose에 태그를 명시한다 (추적성). 릴리즈 진행은 `/private-release` 스킬이 담당한다.
- **롤백** = 직전 태그로 compose 재기동 — prod compose의 이미지 태그를 직전 값으로 되돌려 `up -d`. 직전 태그는 QA 리포트에 기록해 둔다.
- DB 마이그레이션이 포함된 배포의 롤백은 [private-db-schema-convention](./private-db-schema-convention.md)의 역방향 DDL 절차를 따른다 (expand-contract 전제라 코드 롤백만으로 안전한 것이 기본).

## 참고 문서

- [private-tdd](./private-tdd.md) — Release Scenario 섹션 (무중단 배포 시나리오)
- [private-kafka-convention](./private-kafka-convention.md) / [private-redis-convention](./private-redis-convention.md) — compose 인프라 설정
