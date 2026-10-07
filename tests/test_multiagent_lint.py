#!/usr/bin/env python3
"""멀티에이전트 정합 lint 테스트 — 어댑터↔런타임 · 교차 검증 · exec 접근등급.

실행: python3 tests/test_multiagent_lint.py
"""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_module(rel, name):
    path = os.path.join(ROOT, rel)
    spec = importlib.util.spec_from_loader(
        name, importlib.machinery.SourceFileLoader(name, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


h = load_module("bin/harness", "harness_cli")
a = load_module("orchestration/runner/adapter.py", "harness_adapter")

failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        failures.append(name)
        print(f"  FAIL {name}" + (f" — {detail}" if detail else ""))


def run_lint(roles):
    """lint_multiagent 를 격리 실행해 오류 건수를 센다."""
    h.errors.clear()
    h.warns.clear()
    h.lint_multiagent(roles)
    return list(h.errors), list(h.warns)


def real_roles():
    with open(os.path.join(ROOT, "roles.json")) as f:
        return json.load(f)


print("── 실제 roles.json ──")

roles = real_roles()
errs, _ = run_lint(roles)
check("현행 roles.json 은 통과", errs == [], str(errs))

adapters = a.load_adapters()
check("어댑터 id 가 runtimes 키의 부분집합",
      set(adapters) <= set(roles["runtimes"]), f"{sorted(adapters)} vs {sorted(roles['runtimes'])}")
check("host 를 뺀 모든 런타임에 어댑터 존재",
      {r for r in roles["runtimes"] if r != "host"} <= set(adapters),
      f"{sorted(roles['runtimes'])} vs {sorted(adapters)}")

print("── 어댑터 ↔ 런타임 정합 ──")

bad = real_roles()
bad["runtimes"]["ghost"] = {"level": "L1", "invoke": "x",
                            "models": {"m": {"id": "m", "verified": True}},
                            "tiers": {"T1": {"model": "m"}, "T2": {"model": "m"},
                                      "T3": {"model": "m"}}}
errs, warns = run_lint(bad)
check("어댑터 없는 런타임은 지적", any("ghost" in e for e in errs + warns), str(errs + warns))

print("── 교차 검증 강제 ──")

# 검증자와 피검증자가 같은 런타임이면 같은 맹점을 공유한다.
# 지금까지 관례였을 뿐이라 프로파일을 편집하면 조용히 깨졌다.
bad = real_roles()
bad["bindings"]["cross-review"]["review.code"] = {"runtime": "claude", "tier": "T1"}
errs, _ = run_lint(bad)
check("검증자·피검증자 런타임 동일 시 실패",
      any("review.code" in e and "맹점" in e for e in errs), str(errs))

bad = real_roles()
bad["roles"]["review.code"]["verifies"] = ["implement.nope"]
errs, _ = run_lint(bad)
check("없는 role 을 verifies 로 가리키면 실패",
      any("implement.nope" in e for e in errs), str(errs))

# claude-only 는 정의상 교차가 불가능하다 — 예외를 선언 없이 허용하면 검사가 무의미해진다.
check("claude-only 에 면제 선언 존재",
      roles["bindings"]["claude-only"].get("_cross_review_exempt") is True,
      str(roles["bindings"]["claude-only"].get("_cross_review_exempt")))

bad = real_roles()
del bad["bindings"]["claude-only"]["_cross_review_exempt"]
errs, _ = run_lint(bad)
check("면제 선언 없으면 claude-only 도 실패",
      any("claude-only" in e for e in errs), str(errs))

print("── exec 접근 등급 ──")

check("모든 role 에 exec.access",
      all("access" in (r.get("exec") or {}) for r in roles["roles"].values()),
      str([k for k, v in roles["roles"].items() if "access" not in (v.get("exec") or {})]))

for name, ad in adapters.items():
    access = ad.get("access") or {}
    check(f"{name}: access 3등급 선언",
          {"read-only", "workspace-write", "full"} <= set(access), str(sorted(access)))

levels = {r["exec"]["access"] for r in roles["roles"].values()}
check("선언된 등급이 어댑터에 전부 존재",
      all(lv in (adapters["claude"].get("access") or {}) for lv in levels), str(levels))

bad = real_roles()
bad["roles"]["review.code"]["exec"] = {"access": "god-mode"}
errs, _ = run_lint(bad)
check("없는 접근 등급은 실패", any("god-mode" in e for e in errs), str(errs))

# 리뷰·검증 role 이 쓰기 권한을 들면 자기가 검증할 대상을 고칠 수 있다.
REVIEWERS = {"prd.review", "design.review", "review.code", "review.infra"}
offenders = {k for k in REVIEWERS if roles["roles"][k]["exec"]["access"] != "read-only"}
check("리뷰 role 은 read-only", offenders == set(), str(sorted(offenders)))

# 구현 role 은 빌드 도구가 홈 캐시를 써야 하므로 full 이 필요하다 (샌드박스면 테스트를 못 돌린다).
impl = {k: v["exec"]["access"] for k, v in roles["roles"].items() if k.startswith("implement.")}
check("구현 role 은 full 접근", set(impl.values()) == {"full"}, str(impl))

print("── 접근 등급 해소 ──")

resolved = a.resolve_access(adapters["claude"], "read-only")
check("claude read-only → dontAsk", resolved.get("permission_mode") == "dontAsk", str(resolved))
resolved = a.resolve_access(adapters["codex"], "workspace-write")
check("codex workspace-write → sandbox", resolved.get("sandbox") == "workspace-write",
      str(resolved))
try:
    a.resolve_access(adapters["claude"], "nope")
    check("없는 등급은 예외", False, "예외 없음")
except a.AdapterError as e:
    check("없는 등급은 예외", "nope" in str(e), str(e))

print("── 미지원 키 투영 ──")

spec, notes = a.project_exec({"id": "n", "runtime": "codex"},
                             {"access": "read-only", "tools": ["Read", "Bash"]},
                             adapters["codex"])
check("codex 는 tools 미지원 → 제거", "tools" not in spec, str(spec))
check("제거 사실 기록", any("tools" in n for n in notes), str(notes))
check("접근 등급은 반영", spec.get("sandbox") == "read-only", str(spec))

spec, notes = a.project_exec({"id": "n", "runtime": "claude"},
                            {"access": "full", "tools": ["Read", "Write"]},
                            adapters["claude"])
check("claude 는 tools 유지", spec.get("tools") == ["Read", "Write"], str(spec))
check("claude full → bypassPermissions",
      spec.get("permission_mode") == "bypassPermissions", str(spec))
check("제거 없음", notes == [], str(notes))

print("── invoke 문자열이 접근 등급을 반영 ──")

import subprocess
HARNESS_BIN = os.path.join(ROOT, "bin", "harness")


def role_invoke(role):
    out = subprocess.run([sys.executable, HARNESS_BIN, "role", role, "--json"],
                         capture_output=True, text=True, cwd=ROOT)
    return json.loads(out.stdout)[0]


# design.be 는 설계 문서를 쓴다 — read-only 로 나가면 산출물을 만들 수 없다.
inv = role_invoke("design.be")
check("design.be 는 workspace-write", inv.get("access") == "workspace-write", str(inv.get("access")))
check("codex invoke 에 workspace-write 반영",
      "workspace-write" in inv["invoke"], inv["invoke"][:200])

# 리뷰는 read-only 여야 한다 — 검증 대상을 고칠 수 없어야 한다.
inv = role_invoke("review.code")
check("review.code invoke 는 read-only", "-s read-only" in inv["invoke"], inv["invoke"][:200])

# implement 는 claude/Agent 경로 — 헤드리스 argv 가 아니다.
inv = role_invoke("implement.be")
check("implement.be 는 Agent 툴 경로", inv["invoke"].startswith("Agent("), inv["invoke"][:80])

print("── 그래프 프롬프트 위생 ──")

real_graph = json.load(open(os.path.join(ROOT, "orchestration/private-feature.json")))
for node in real_graph["nodes"]:
    prompt = node.get("prompt") or ""
    check(f"{node['id']}: prompt 존재", bool(prompt.strip()))
    # 리터럴 \n 은 줄바꿈으로 렌더되지 않아 섹션이 한 줄로 뭉친다 (오류는 안 난다).
    check(f"{node['id']}: 리터럴 개행 없음", "\\n" not in prompt, prompt[:60])
    # 머신 절대경로가 박히면 다른 머신에서 깨진다 — 경로 규칙은 rules/ 가 정본이다.
    check(f"{node['id']}: 머신 경로 없음", "/Users/" not in prompt, prompt[:60])

print("── 컴파일 산출물 비오염 ──")

# __pycache__ 의 .pyc 는 소스 절대경로를 품어 "머신 절대경로 비의존" rubric 을 깨뜨린다.
# 러너를 로드해도 남지 않아야 한다.
import glob
for stale in glob.glob(os.path.join(ROOT, "**", "__pycache__"), recursive=True):
    if ".git" not in stale:
        shutil.rmtree(stale, ignore_errors=True)
h.load_runner("adapter")
h.load_runner("dispatch")
h.load_runner("wave")
left = [d for d in glob.glob(os.path.join(ROOT, "orchestration", "**", "__pycache__"),
                            recursive=True)]
check("러너 로드가 .pyc 를 남기지 않는다", left == [], str(left))

print()
if failures:
    print(f"실패 {len(failures)}건: {failures}")
    sys.exit(1)
print("전부 통과")
