# adapters/cursor — 미구현 스텁

`~/.cursor/hooks.json`이 존재해 훅 강제는 가능해 보이지만, Cursor는 규칙이 주로 **레포 로컬**(`.cursor/rules`, glob 스코프)이라 전역 하네스 투영 모델이 다르다. 확인 전까지 구현하지 않는다.

## 구현할 때 필요한 것

1. `~/.cursor/hooks.json` 스키마 확인 (`hooks.json.bak`에 실제 샘플 있음)
2. 전역 규칙 주입 지점 확인 — 전역 rules가 없다면 레포별 `.cursor/rules` 생성 방식으로 전략 변경
3. `capabilities.json` 작성 — `spawn_subagent`·`mcp` 실측

## 주의

레포별 투영이 되면 SSOT 원칙상 **생성물**이므로 각 레포의 `.cursor/rules`를 `.gitignore`에 넣을지 결정해야 한다. 이 결정은 ADR로 남긴다.
