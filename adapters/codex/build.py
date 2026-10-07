#!/usr/bin/env python3
"""codex 어댑터 — policy.json → ~/.codex/AGENTS.md + hooks.json (+ config.toml 제안)

안전 원칙 (capabilities.json 의 unowned 참조):
  - config.toml 은 하네스가 소유하지 않는다. 제안 fragment만 .out/ 에 출력하고 절대 적용하지 않는다.
  - hooks.json 의 matcher 지원이 미확인이므로 matcher 를 넣지 않는다.
    matcher 에 의존하던 게이트는 스크립트 자체 가드가 검증되기 전까지 --install 대상에서 제외된다.
  - skills 는 디렉토리 통째가 아니라 항목 단위로 링크한다 (기존 외부 스킬 보존).
"""
import json, os, shutil, sys, datetime

HARNESS = os.path.expanduser("~/.harness")
OUT = os.path.join(HARNESS, "adapters/codex/.out")
CODEX = os.path.expanduser("~/.codex")
TARGET_HOOKS = os.path.join(CODEX, "hooks.json")
TARGET_AGENTS = os.path.join(CODEX, "AGENTS.md")
MARKER = os.path.join(CODEX, ".harness-build.json")

ORCA_MARK = "/.orca/agent-hooks/"


def load(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def build_hooks(policy):
    """matcher 없이 등록 가능한 게이트만 생성. matcher 의존 게이트는 보류 목록으로 반환."""
    existing = (load(TARGET_HOOKS, {}) or {}).get("hooks", {})
    preserved = {ev: entries for ev, entries in existing.items() if entries}

    registered, deferred = {}, []
    for gate in policy.get("gates", []):
        matcher = (gate.get("matcher") or "").strip()
        if matcher and matcher not in ("*", ""):
            deferred.append(gate)          # 툴 필터가 필요한데 지원 여부 미확인
            continue
        registered.setdefault(gate["event"], []).append({
            "type": "command",
            "command": f"{HARNESS}/hooks/{os.path.basename(gate['script'])}",
            "timeout": 30,
        })

    result = {}
    for event in sorted(set(registered) | set(preserved)):
        entries = []
        if event in registered:
            entries.append({"hooks": registered[event]})
        entries.extend(preserved.get(event, []))
        result[event] = entries
    return {"hooks": result}, deferred, sum(len(v) for v in preserved.values())


def build_agents_md(policy, deferred):
    lines = [
        "<!-- 생성 파일 — 직접 수정하지 마세요. -->",
        f"<!-- SSOT: {HARNESS} -->",
        f"<!-- 재생성: {HARNESS}/bin/harness build --runtime codex --install -->",
        "",
        "# AGENTS",
        "",
        f"이 세션의 작업 하네스 SSOT는 `{HARNESS}` 입니다.",
        f"세션 시작 시 [{HARNESS}/HARNESS.md]({HARNESS}/HARNESS.md) 의 **진입 절차**를 따르세요.",
        "",
        "## 적합성",
        "",
        "이 런타임은 **L1** 입니다 — 서브에이전트 스폰이 확인되지 않았습니다.",
        f"L2를 요구하는 그래프는 [{HARNESS}/capabilities.md]({HARNESS}/capabilities.md) 의 **강등 사다리**를 따라",
        "같은 세션 내 페르소나 순차 전환으로 직렬 실행하고, 그 사실을 산출물의 `degraded` 필드에 남깁니다.",
        "",
        "## 필수 로드",
        "",
        f"- `{HARNESS}/rules/00-core-directives.md` — 항상 로드",
        f"- 나머지 `{HARNESS}/rules/*.md` — 필요한 것만 선택 로드 (전량 로드 금지)",
        "",
        "## 훅 강제 상태",
        "",
    ]
    if deferred:
        lines += [
            f"게이트 {len(deferred)}개가 **훅으로 등록되지 않았습니다** (툴 필터 지원 미확인).",
            "아래 게이트는 해당 작업 직전에 `fallback` 절차로 대체해야 합니다.",
            "`blocking`은 스크립트를 직접 실행해 exit code를 확인하고, `ask`는 사용자 승인 단계를 넣습니다.",
            "",
            "| 게이트 | 등급 | 대상 | 대체 절차 |",
            "|---|---|---|---|",
        ]
        for g in deferred:
            lines.append(f"| `{g['id']}` | {g['enforcement']} | `{g.get('matcher','')}` | "
                         f"{g.get('fallback') or '—'} |")
        lines.append("")
    else:
        lines += ["모든 게이트가 훅으로 등록되었습니다.", ""]
    lines += [
        "## 규칙 우선순위",
        "",
        f"[{HARNESS}/HARNESS.md]({HARNESS}/HARNESS.md) 의 우선순위 표를 따릅니다.",
        "",
    ]
    return "\n".join(lines) + "\n"


def build_config_suggestion(policy):
    perms = policy.get("permissions", {})
    return (
        "# 제안 fragment — 하네스는 config.toml 을 소유하지 않습니다.\n"
        "# 검토 후 직접 반영하세요. `harness build` 는 이 파일을 적용하지 않습니다.\n"
        f"# 생성: {datetime.date.today().isoformat()}\n\n"
        f"# policy.json 의 permissions.allow {len(perms.get('allow', []))}개 항목은\n"
        "# codex 의 sandbox/approval 모델과 1:1 대응하지 않습니다.\n"
        "# 대응 규칙을 정한 뒤 ADR 로 남기고 이 fragment 를 채우세요.\n"
    )


def main():
    install = "--install" in sys.argv
    policy = load(os.path.join(HARNESS, "policy.json"))
    if policy is None:
        sys.exit("policy.json 없음")

    hooks, deferred, preserved_n = build_hooks(policy)
    agents_md = build_agents_md(policy, deferred)

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "hooks.json"), "w") as f:
        json.dump(hooks, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(os.path.join(OUT, "AGENTS.md"), "w") as f:
        f.write(agents_md)
    with open(os.path.join(OUT, "config.toml.suggested"), "w") as f:
        f.write(build_config_suggestion(policy))

    registered_n = sum(len(e.get("hooks", [])) for ev in hooks["hooks"].values() for e in ev)
    print(f"[codex] 훅 등록 {registered_n - preserved_n}개 / 보류 {len(deferred)}개 (matcher 지원 미확인) "
          f"/ 기존 보존 {preserved_n}개")
    print(f"[codex] config.toml 은 적용 대상 아님 — 제안 fragment만 출력")

    if not install:
        print(f"[codex] 드라이런 — 산출물: {OUT}  (적용하려면 --install)")
        return 0

    for target, content in ((TARGET_HOOKS, json.dumps(hooks, indent=2, ensure_ascii=False) + "\n"),
                            (TARGET_AGENTS, agents_md)):
        if os.path.exists(target):
            shutil.copy2(target, target + ".pre-harness.bak")
        with open(target, "w") as f:
            f.write(content)
        print(f"[codex] 적용: {target}")

    # skills 항목 단위 링크 — 기존 비하네스 스킬은 건드리지 않는다
    skills_dir = os.path.join(CODEX, "skills")
    os.makedirs(skills_dir, exist_ok=True)
    linked = 0
    for name in sorted(os.listdir(os.path.join(HARNESS, "skills"))):
        src, dst = os.path.join(HARNESS, "skills", name), os.path.join(skills_dir, name)
        if os.path.islink(dst):
            if os.readlink(dst) == src:
                continue
            os.unlink(dst)
        elif os.path.exists(dst):
            print(f"[codex] 건너뜀(실파일 존재): {dst}")
            continue
        os.symlink(src, dst)
        linked += 1
    print(f"[codex] skills 심링크 {linked}개 생성")

    with open(MARKER, "w") as f:
        json.dump({
            "harness_version": policy.get("version"),
            "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "deferred_gates": [g["id"] for g in deferred],
            "do_not_edit": ["hooks.json", "AGENTS.md"],
        }, f, indent=2, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
