#!/usr/bin/env python3
"""/private-implement 교차 런타임 TDD 파이프라인 계약 테스트.

흐름: worktree → 컨텍스트 분석(A‖B 독립) → RED(B) → GREEN/REFACTOR(A)
      → 결정적 게이트 → 교차 리뷰(B) ⟲ 최대 2회 → draft PR → 회고

불변식은 스킬 문구가 아니라 roles.json 의 verifies 로 강제한다 — 문구는 관례라
프로파일을 편집하면 조용히 깨진다. 스킬 본문 검사는 핵심 게이트의 존재만 본다.

실행: python3 tests/test_private_implement_pipeline.py
"""
import importlib.machinery
import importlib.util
import json
import os
import re
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
failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        failures.append(name)
        print(f"  FAIL {name}" + (f" — {detail}" if detail else ""))


def real_roles():
    with open(os.path.join(ROOT, "roles.json")) as f:
        return json.load(f)


def run_multiagent_lint(roles):
    h.errors.clear()
    h.warns.clear()
    h.lint_multiagent(roles)
    return list(h.errors)


def runtime_of(roles, role, profile="cross-review"):
    return h.resolve_routing(roles, role, None, profile)["runtime"]


roles = real_roles()
defs = roles["roles"]
NEW_ROLES = ("analyze.context", "analyze.cross", "test.red")

print("── 신규 role 정의 ──")

for name in NEW_ROLES:
    check(f"role '{name}' 존재", name in defs, str(sorted(defs)))

for name in NEW_ROLES:
    agent = (defs.get(name) or {}).get("agent", "")
    path = os.path.join(ROOT, "agents", agent + ".md")
    check(f"role '{name}' 의 agent 파일 존재", bool(agent) and os.path.exists(path), path)

# 분석은 대상 레포를 고치지 않는다 — 산출물은 run 디렉토리 파일 하나뿐이다.
for name in ("analyze.context", "analyze.cross"):
    access = ((defs.get(name) or {}).get("exec") or {}).get("access")
    check(f"'{name}' 은 레포 코드를 쓰지 않는 workspace-write", access == "workspace-write", str(access))

# RED 는 테스트를 실행하고 커밋까지 해야 한다.
access = ((defs.get("test.red") or {}).get("exec") or {}).get("access")
check("'test.red' 는 테스트 실행·커밋 가능한 full", access == "full", str(access))

print("── 교차 런타임 불변식 (verifies 선언) ──")

check("analyze.cross 가 analyze.context 를 verifies",
      "analyze.context" in ((defs.get("analyze.cross") or {}).get("verifies") or []))
for impl in ("implement.be", "implement.fe"):
    check(f"{impl} 이 test.red 를 verifies (테스트 이의 제기 주체)",
          "test.red" in ((defs.get(impl) or {}).get("verifies") or []))
check("review.code 는 계속 implement.be 를 verifies",
      "implement.be" in ((defs.get("review.code") or {}).get("verifies") or []))

print("── cross-review 프로파일 해석 ──")

if all(n in defs for n in NEW_ROLES):
    check("분석 A·B 런타임이 다름",
          runtime_of(roles, "analyze.context") != runtime_of(roles, "analyze.cross"))
    check("RED 런타임 ≠ GREEN 런타임",
          runtime_of(roles, "test.red") != runtime_of(roles, "implement.be"))
    check("리뷰 런타임 ≠ GREEN 런타임",
          runtime_of(roles, "review.code") != runtime_of(roles, "implement.be"))
    check("현행 roles.json 은 멀티에이전트 lint 통과", run_multiagent_lint(roles) == [])

    bad = real_roles()
    bad["bindings"]["cross-review"]["test.red"] = dict(
        bad["bindings"]["cross-review"]["implement.be"])
    errs = run_multiagent_lint(bad)
    check("RED 를 GREEN 과 같은 런타임에 두면 lint 실패",
          any("test.red" in e and "맹점" in e for e in errs), str(errs))

    bad = real_roles()
    bad["bindings"]["cross-review"]["analyze.cross"] = dict(
        bad["bindings"]["cross-review"].get("analyze.context") or {"runtime": "claude", "tier": "T1"})
    errs = run_multiagent_lint(bad)
    check("분석 A·B 를 같은 런타임에 두면 lint 실패",
          any("analyze.context" in e and "맹점" in e for e in errs), str(errs))

print("── implementer 교차 TDD 모드 ──")

# 기존 페르소나는 RED 를 스스로 쓴다. RED 커밋을 받는 모드가 없으면
# GREEN 작성자가 테스트를 다시 쓰거나 고쳐 통과시킨다.
for agent in ("private-be-implementer", "private-fe-implementer"):
    text = open(os.path.join(ROOT, "agents", agent + ".md"), encoding="utf-8").read()
    check(f"{agent}: 교차 TDD 모드 섹션", "교차 TDD 모드" in text)
    check(f"{agent}: 테스트 이의 절차", "테스트 이의" in text)

print("── /private-implement 스킬 계약 ──")

skill_path = os.path.join(ROOT, "skills/private-implement/SKILL.md")
body = open(skill_path, encoding="utf-8").read()
declared = h.fm_list(h.frontmatter(skill_path), "roles")
for name in NEW_ROLES:
    check(f"스킬 frontmatter roles 에 '{name}'", name in declared, str(declared))
for name in NEW_ROLES:
    check(f"스킬 라우팅 명령에 '{name}'",
          re.search(r"harness role --compact[^\n`]*\b" + re.escape(name) + r"\b", body) is not None)

gates = {
    "worktree 준비": r"worktree",
    "분석 모호성 사용자 게이트": r"사용자 게이트",
    "RED 실패 원인 = 미구현 확인": r"미구현",
    "GREEN 단계 테스트 diff 0": r"테스트 (파일 )?diff\s*=?\s*0",
    "테스트 이의 반려 경로": r"테스트 이의",
    "결정적 게이트 (lint+test+build)": r"결정적 게이트",
    "리뷰 입력은 티켓+확정사항+diff": r"사용자 확정 사항",
    "통과 기준 p0~p3 0건": r"통과 기준: p0~p3\s*0건",
    "p3 는 REFACTOR 로만, 재작업 횟수 제외": r"p3.{0,80}재작업 횟수에 세지 않는다",
    "리뷰 통과 SHA 기록": r"reviewed_sha",
    "머지 단계는 사용자 확인 후": r"Step 9.{0,40}머지",
    "머지 전 PR HEAD == reviewed_sha 확인": r"headRefOid",
    "draft 해제 후 머지": r"gh pr ready",
    "머지 토큰 p3-reflected": r"gh pr merge[^\n]*# p3-reflected",
    "재작업 루프 최대 2회": r"최대 2회",
    "draft PR": r"--draft",
    "실패 시에도 회고": r"실패.{0,40}회고|회고.{0,40}실패",
}
for label, pattern in gates.items():
    check(f"스킬 본문: {label}", re.search(pattern, body) is not None, pattern)

print("── codex invoke 는 frontmatter 페르소나를 옵션으로 넘기지 않는다 ──")

# 회귀: 페르소나가 `---` 로 시작해 argv 로 넘기면 codex(clap)가 옵션으로 파싱해
# `unexpected argument '---'` 로 즉시 죽었다 (runs/private-implement/20261007-…/retro.md).
# 가짜 codex 로 invoke 를 실제 셸에서 돌려 argv·stdin 이 어떻게 전달되는지 본다.
import subprocess
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    fake = os.path.join(tmp, "codex")
    with open(fake, "w") as f:
        f.write("#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "d = os.environ['FAKE_CODEX_OUT']\n"
                "json.dump(sys.argv[1:], open(os.path.join(d, 'argv.json'), 'w'))\n"
                "open(os.path.join(d, 'stdin.txt'), 'w').write(sys.stdin.read())\n")
    os.chmod(fake, 0o755)
    roles_doc = h.load("roles.json")
    resolved = h.resolve_routing(roles_doc, "analyze.cross", profile_name="cross-review")
    command = h.invoke_command(resolved, prompt="작업 지시", roles=roles_doc)
    env = dict(os.environ, PATH=f"{tmp}:{os.environ['PATH']}", FAKE_CODEX_OUT=tmp)
    run = subprocess.run(["bash", "-c", command], env=env, stdin=subprocess.DEVNULL,
                         capture_output=True, text=True)
    check("invoke 셸 실행 성공", run.returncode == 0, run.stderr[:200])
    argv = json.load(open(os.path.join(tmp, "argv.json"))) if run.returncode == 0 else []
    stdin = open(os.path.join(tmp, "stdin.txt")).read() if run.returncode == 0 else ""
    check("argv 에 페르소나 본문이 없다", not any(a.startswith("---") for a in argv), str(argv)[:200])
    check("프롬프트는 stdin 마커 `-` 로 받는다", argv[-1:] == ["-"], str(argv[-3:]))
    check("stdin 에 페르소나 frontmatter + 작업 지시", stdin.startswith("---") and "작업 지시" in stdin,
          stdin[:80])

print("── /private-review 제거: 머지 게이트는 /private-implement·/private-feature 리뷰 루프가 소유 ──")

check("skills/private-review 디렉토리 없음",
      not os.path.exists(os.path.join(ROOT, "skills", "private-review")))
stale = []
for sub in ("agents", "skills", "rules", "hooks", "commands", "orchestration"):
    for dirpath, _dirs, names in os.walk(os.path.join(ROOT, sub)):
        for name in names:
            path = os.path.join(dirpath, name)
            try:
                text = open(path, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            if "/private-review" in text or "skills/private-review" in text:
                stale.append(os.path.relpath(path, ROOT))
check("하네스 정의에 /private-review 참조 0건", stale == [], str(stale))

print("── 정적 lint 전체 (스킬·에이전트 섹션) ──")

h.errors.clear()
h.warns.clear()
loaded = h.lint_roles()
h.lint_agents(loaded)
h.lint_agent_sections(loaded)
h.lint_skills(loaded)
h.lint_readmes()
check("roles·agents·skills·README lint 오류 0", h.errors == [], str(h.errors))

print()
if failures:
    print(f"실패 {len(failures)}건")
    sys.exit(1)
print("전부 통과")
