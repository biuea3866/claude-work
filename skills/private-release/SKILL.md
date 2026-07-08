---
name: private-release
description: 개인 프로젝트 prod 릴리즈 — private-qa로 배포 가부를 조사하고, PASS면 YYYYMMDD-NN 태그를 따서 prod 프로필로 배포한다. QA FAIL이면 배포 불가. 인수로 대상 기능/앱 카테고리를 받는다(없으면 현재 브랜치 기준).
user-invocable: true
---

릴리즈 대상: $ARGUMENTS  (기능명·앱 카테고리 / 비어있으면 현재 브랜치·레포 기준)

현재 브랜치: !`git branch --show-current 2>/dev/null || echo "(git 없음)"`
개인 프로젝트 마커: !`[ -f "$(git rev-parse --show-toplevel 2>/dev/null)/.claude/private-project" ] && echo "OK" || echo "없음"`
오늘 날짜: !`date +%Y%m%d`
당일 기존 릴리즈 태그: !`git tag -l "$(date +%Y%m%d)-*" 2>/dev/null | sort || echo "(없음)"`
prod compose 파일: !`ls -1 docker-compose.prod.yml docker-compose.prod.yaml 2>/dev/null || echo "(루트에 없음 — --profile prod 사용 여부 확인)"`

---

개인 프로젝트 전용 prod 릴리즈 진입점. 마커가 없으면 회사용 배포 절차를 안내하고 중단한다.

배포 규칙 SSOT: `~/.claude/rules/private-deploy-convention.md`. 이 스킬은 그 규칙의 실행 절차다.

> **불변 조건**: private-qa verdict PASS 없이는 prod 배포하지 않는다. hook `private-prod-deploy-gate.sh`가 `# qa-passed` 토큰으로 강제하며, PASS 없이 토큰만 붙이는 것은 거짓 단언(COMPLETION-RULE 위반, 감사 대상)이다.

## Step 1 — 사전 확인

1. 마커가 없으면 중단하고 안내한다.
2. prod 배포 대상은 **`main`에 머지되어 dev 환경에 배포된 것**이다. `main` 미반영이면 릴리즈 대상이 아니므로 중단하고 main 반영(`/private-review` 머지 → dev 환경 배포)을 먼저 안내한다.
3. prod compose 식별자를 확정한다: `docker-compose.prod.yml`(표준) 또는 `--profile prod`. 둘 다 없으면 사용자에게 확인하고 중단한다 (임의로 dev compose를 prod로 쓰지 않는다).

## Step 2 — QA 게이트 (배포 가부 조사)

`Agent(private-qa)` — 릴리즈 대상 기능을 dev에서 실구동 E2E(신규 시나리오 + 회귀 카탈로그 전체)로 검증한다.

- **verdict FAIL** → 릴리즈 중단. 버그·회귀 항목을 그대로 보고하고, 담당 implementer 수정 → dev 재배포 → **QA 전체 재실행**을 안내한다. 부분 재검증으로 배포를 진행하지 않는다.
- **verdict PASS** → Step 3으로. QA 리포트 경로와 **직전 prod 이미지 태그**(롤백 지점)를 확보한다.

## Step 3 — 릴리즈 태그 결정 (YYYYMMDD-NN)

- 형식: `{오늘YYYYMMDD}-{NN}` — NN은 당일 시퀀스(2자리 zero-pad, `01`부터).
- 위 "당일 기존 릴리즈 태그"에서 최대 시퀀스를 찾아 +1 한다. 당일 태그가 없으면 `-01`.
- git 태그와 docker 이미지 태그를 **동일 값**으로 쓴다 — 추적성 확보. `latest` 금지 (컨벤션).
- 태그 문자열을 사용자에게 명시하고 진행한다.

## Step 4 — 이미지 빌드 + 태그 고정

1. prod 이미지를 릴리즈 태그로 빌드한다 (compose의 `image:`에 태그 반영 또는 `docker build -t <이미지>:<YYYYMMDD-NN>`). `latest` 태그를 붙이지 않는다.
2. compose 파일이 `latest`·미고정 태그를 참조하면 릴리즈 태그로 교정한다 (이 변경은 릴리즈 커밋 대상).
3. 빌드 결과를 exit code로 확인한다 — 실패 시 중단 (`| tail` 금지, `set -o pipefail` 또는 `BUILD SUCCESSFUL` 직접 확인).

## Step 5 — prod 배포

QA PASS를 확인한 뒤에만 토큰을 붙여 배포한다:

```
docker compose -f docker-compose.prod.yml up -d   # qa-passed
```

- `--profile prod`를 쓰는 레포는 동일하게 토큰을 붙인다.
- 배포 후 `docker compose -f docker-compose.prod.yml ps`로 컨테이너 기동을 확인하고, 핵심 헬스체크(HTTP 200·로그)를 1회 실행한다.

## Step 6 — 태그 기록 + 롤백 지점

1. git 태그를 만든다 (annotated): `git tag -a <YYYYMMDD-NN> -m "release: {기능명}"`. 사용자가 원하면 `git push origin <태그>`.
2. **롤백 지점**을 QA 리포트에 기록한다: 직전 prod 이미지 태그 = 롤백 대상. 롤백 = prod compose의 이미지 태그를 직전 값으로 되돌려 `up -d`.
3. DB 마이그레이션이 포함된 릴리즈면 expand-contract 전제상 코드 롤백만으로 안전한지 확인하고, 아니면 역방향 DDL 절차(`private-db-schema-convention.md`)를 롤백 노트에 명시한다.

## 보고

> 완료 단언은 `rules/COMPLETION-RULE.md` §1~4를 모두 충족해야 한다. "배포 완료"는 배포 명령 raw 출력 + `ps` 출력이 같은 메시지에 있어야 인정된다.

```
## /private-release 결과: {완료 | 중단(QA FAIL) | in-progress}
- QA: {verdict + 리포트 경로}
- 릴리즈 태그: {YYYYMMDD-NN} (git + 이미지 동일)
- 배포: {prod 배포 명령 + up -d / ps raw 출력}
- 롤백 지점: {직전 이미지 태그 — 롤백 명령}
- 다음: {QA FAIL이면 수정 항목 / 태그 push 여부}
```
