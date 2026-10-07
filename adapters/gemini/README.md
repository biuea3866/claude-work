# adapters/gemini — 미구현 스텁

현재 `~/.gemini`에는 `settings.json`·`config/`만 있고 하네스 연동 흔적이 없다. 능력이 확인되지 않은 상태에서 설정을 생성하면 조용히 깨지므로 **의도적으로 구현하지 않았다**.

## 구현할 때 필요한 것

1. `capabilities.json` 작성 — 아래를 실제로 확인한 뒤 채운다.
   - 훅 이벤트 지원 여부 (`hook_enforce`)
   - 서브에이전트 스폰 지원 여부 (`spawn_subagent`)
   - 전역 지침 파일 경로 (`~/.gemini/GEMINI.md` 추정 — **확인 필요**)
2. `build.py` — `policy.json` → `~/.gemini/settings.json` 매핑. 권한 스키마 대조 필요.
3. 링크 전략 결정 — `~/.gemini`에 rules/skills 개념이 있는지부터 확인.

## 확인 방법

```bash
bin/harness doctor --runtime gemini
```

능력 확인 전까지 `capabilities.md`의 런타임 매트릭스에서 gemini는 전부 `probe`로 남는다.
