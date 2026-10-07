#!/usr/bin/env python3
"""claude-code 어댑터 — policy.json → ~/.claude/settings.json + CLAUDE.md

기본은 드라이런: 산출물을 adapters/claude-code/.out/ 에 쓰고 요약만 출력한다.
--install 을 줘야 실제 런타임 경로에 적용한다 (적용 전 .bak 백업).

핵심 규칙: settings.json 은 공동 소유다. 하네스가 소유한 훅
($HOME/.claude/hooks/*.sh)만 교체하고, Orca 등 외부 주입 항목은 보존한다.
"""
import json, os, re, shutil, sys, datetime

HARNESS = os.path.expanduser("~/.harness")
OUT = os.path.join(HARNESS, "adapters/claude-code/.out")
TARGET_SETTINGS = os.path.expanduser("~/.claude/settings.json")
TARGET_CLAUDE_MD = os.path.expanduser("~/.claude/CLAUDE.md")
MARKER = os.path.expanduser("~/.claude/.harness-build.json")

HARNESS_HOOK = re.compile(r"^\$HOME/\.claude/hooks/[A-Za-z0-9._-]+\.sh$")
OWNED_KEYS = {"env", "model", "effortLevel", "permissions", "hooks"}


def load(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def build_hooks(policy, existing_hooks):
    """하네스 게이트를 재생성하고, 외부 주입 훅은 원형 그대로 보존한다."""
    preserved, foreign_count = {}, 0
    for event, entries in (existing_hooks or {}).items():
        kept = []
        for entry in entries:
            others = [h for h in entry.get("hooks", [])
                      if not HARNESS_HOOK.match(h.get("command", "").strip())]
            if others:
                new_entry = dict(entry)
                new_entry["hooks"] = others
                kept.append(new_entry)
                foreign_count += len(others)
        if kept:
            preserved[event] = kept

    # 하네스 게이트를 (event, matcher)로 묶는다
    owned = {}
    for gate in policy.get("gates", []):
        event, matcher = gate["event"], gate.get("matcher", "")
        bucket = owned.setdefault(event, {})
        bucket.setdefault(matcher, []).append({
            "type": "command",
            "command": "$HOME/.claude/hooks/" + os.path.basename(gate["script"]),
        })

    result, owned_count = {}, 0
    for event in sorted(set(owned) | set(preserved)):
        entries = []
        for matcher, hooks in owned.get(event, {}).items():
            entries.append({"matcher": matcher, "hooks": hooks})  # 차단 게이트를 먼저 실행
            owned_count += len(hooks)
        entries.extend(preserved.get(event, []))
        result[event] = entries
    return result, owned_count, foreign_count


SECRET_REF = re.compile(r"\$\{secrets\.([A-Za-z0-9_]+)\}")


def resolve_secrets(env):
    """policy.json 의 ${secrets.KEY} 를 secrets.local.json 값으로 치환.

    정의가 없으면 그 키를 **빼고** 경고한다 — 빈 문자열로 넣으면 런타임이
    '설정은 됐는데 값이 틀린' 상태가 돼 원인 추적이 어려워진다.
    """
    store = load(os.path.join(HARNESS, "secrets.local.json"), {}) or {}
    out, missing = {}, []
    for key, value in env.items():
        m = SECRET_REF.fullmatch(str(value))
        if not m:
            out[key] = value
            continue
        if m.group(1) in store:
            out[key] = store[m.group(1)]
        else:
            missing.append(m.group(1))
    for key in missing:
        print(f"[claude-code] 경고: secrets.local.json 에 '{key}' 없음 — 해당 env 를 생략합니다")
    return out


def expand_home(value):
    """$HOME 을 실제 홈으로 편다 — policy.json 은 머신 비의존으로 두고 생성물만 구체화."""
    if isinstance(value, str):
        return value.replace("$HOME", os.path.expanduser("~"))
    if isinstance(value, list):
        return [expand_home(v) for v in value]
    return value


def build_settings(policy):
    existing = load(TARGET_SETTINGS, {}) or {}
    settings = {k: v for k, v in existing.items() if k not in OWNED_KEYS}  # 미지 키 보존

    settings["env"] = resolve_secrets(policy.get("env", {}))
    if policy.get("defaults", {}).get("model"):
        settings["model"] = policy["defaults"]["model"]
    if policy.get("defaults", {}).get("effort"):
        settings["effortLevel"] = policy["defaults"]["effort"]

    perms = {k: expand_home(v) for k, v in policy.get("permissions", {}).items()}
    extra_dirs = expand_home(policy.get("filesystem", {}).get("additional_directories", []))
    if extra_dirs:
        perms["additionalDirectories"] = extra_dirs
    settings["permissions"] = {k: v for k, v in perms.items() if v}

    settings.update(policy.get("runtime_passthrough", {}).get("claude-code", {}))
    hooks, owned_n, foreign_n = build_hooks(policy, existing.get("hooks"))
    settings["hooks"] = hooks
    return settings, owned_n, foreign_n


def build_claude_md():
    """CLAUDE.md = 진입 안내 + 코어 지침 본문. 링크는 빌드 시점에 해석 가능한 경로로 치환."""
    src = os.path.join(HARNESS, "rules/00-core-directives.md")
    with open(src) as f:
        text = f.read()
    if text.startswith("---"):                       # frontmatter 제거
        text = text.split("---", 2)[2].lstrip("\n")
    text = text.replace("](../", f"]({HARNESS}/").replace("](./", "](./rules/")
    header = (
        "<!-- 생성 파일 — 직접 수정하지 마세요. -->\n"
        f"<!-- SSOT: {HARNESS}/rules/00-core-directives.md -->\n"
        f"<!-- 재생성: {HARNESS}/bin/harness build --install -->\n\n"
        f"> 이 세션의 작업 하네스 SSOT는 `{HARNESS}` 입니다.\n"
        f"> 세션 시작 시 [{HARNESS}/HARNESS.md]({HARNESS}/HARNESS.md) 의 **진입 절차**를 따르세요.\n\n"
    )
    return header + text


def main():
    install = "--install" in sys.argv
    policy = load(os.path.join(HARNESS, "policy.json"))
    if policy is None:
        sys.exit("policy.json 없음")

    settings, owned_n, foreign_n = build_settings(policy)
    claude_md = build_claude_md()

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "settings.json"), "w") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(os.path.join(OUT, "CLAUDE.md"), "w") as f:
        f.write(claude_md)

    print(f"[claude-code] 게이트 {owned_n}개 재생성 / 외부 주입 훅 {foreign_n}개 보존")
    print(f"[claude-code] permissions.allow {len(settings['permissions'].get('allow', []))}개, "
          f"이벤트 {len(settings['hooks'])}종")

    if not install:
        print(f"[claude-code] 드라이런 — 산출물: {OUT}  (적용하려면 --install)")
        return 0

    for target, content in ((TARGET_SETTINGS, json.dumps(settings, indent=2, ensure_ascii=False) + "\n"),
                            (TARGET_CLAUDE_MD, claude_md)):
        if os.path.exists(target):
            shutil.copy2(target, target + ".pre-harness.bak")
        with open(target, "w") as f:
            f.write(content)
        print(f"[claude-code] 적용: {target}  (백업: {os.path.basename(target)}.pre-harness.bak)")

    with open(MARKER, "w") as f:
        json.dump({
            "harness_version": policy.get("version"),
            "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "source": os.path.join(HARNESS, "policy.json"),
            "do_not_edit": ["settings.json", "CLAUDE.md"],
        }, f, indent=2, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
