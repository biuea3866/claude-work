#!/usr/bin/env python3
"""/private-roadmap 등록 검증 — 스킬·role·에이전트·바인딩이 하네스 규약대로 연결됐는지.

흐름: 시장 조사(경쟁사·고객 요구) A‖B → 교차 검증 → 신규 아이디어 A‖B → 로드맵 → 과제(PRD) 분리
→ 과제별 PRD 구체화 → PRD 리뷰 → 포트폴리오 충돌 검증 → 과제 확정.
조사·아이디어는 서로 다른 런타임이 독립 실행하고, 작성자와 리뷰어는 다른 런타임에 둔다.

실행: python3 tests/test_private_roadmap_registration.py
"""
import importlib.machinery
import importlib.util
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_harness():
    path = os.path.join(ROOT, "bin", "harness")
    spec = importlib.util.spec_from_loader(
        "harness_cli", importlib.machinery.SourceFileLoader("harness_cli", path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


h = load_harness()
roles = h.load("roles.json")
role_specs = roles.get("roles", {})
bindings = roles.get("bindings", {})

failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        failures.append(name)
        print(f"  FAIL {name}" + (f" — {detail}" if detail else ""))


def runtime_of(profile, role):
    binding = bindings.get(profile, {})
    return (binding.get(role) or binding.get("_default") or {}).get("runtime")


NEW_ROLES = {
    "research.market": "private-market-researcher",
    "research.cross": "private-market-researcher",
    "research.verify": "private-research-verifier",
    "idea.generate": "private-idea-generator",
    "idea.cross": "private-idea-generator",
    "roadmap.author": "private-roadmap-planner",
    "roadmap.split": "private-roadmap-planner",
    "roadmap.review": "private-roadmap-reviewer",
}
SKILL_ROLES = set(NEW_ROLES) | {"prd.author", "prd.review"}

print("role · 에이전트")
for role, agent in NEW_ROLES.items():
    spec = role_specs.get(role) or {}
    check(f"role {role} 존재", bool(spec))
    check(f"role {role} → agent {agent}", spec.get("agent") == agent, repr(spec.get("agent")))
    check(f"agents/{agent}.md 존재",
          os.path.exists(os.path.join(ROOT, "agents", agent + ".md")))

print("교차 런타임 (cross-review 프로파일)")
pairs = [
    ("research.market", "research.cross", "시장 조사 A‖B"),
    ("idea.generate", "idea.cross", "아이디어 A‖B"),
    ("roadmap.author", "roadmap.review", "로드맵 작성 ↔ 리뷰"),
    ("roadmap.split", "roadmap.review", "과제 분리 ↔ 리뷰"),
    ("prd.author", "prd.review", "PRD 작성 ↔ 리뷰"),
]
for a, b, label in pairs:
    ra, rb = runtime_of("cross-review", a), runtime_of("cross-review", b)
    check(f"{label}: 서로 다른 런타임 ({a}={ra}, {b}={rb})", ra and rb and ra != rb)
for role in ("roadmap.author", "roadmap.split", "prd.author"):
    check(f"{role} 은 codex 가 작성", runtime_of("cross-review", role) == "codex",
          repr(runtime_of("cross-review", role)))
prd_binding = bindings.get("cross-review", {}).get("prd.author") or {}
check("prd.author = codex/T1 (과제별 PRD 품질 — terra → sol 상향)",
      prd_binding.get("tier") == "T1", repr(prd_binding))
codex_rt = roles.get("runtimes", {}).get("codex", {})
prd_model_alias = (codex_rt.get("tiers", {}).get(prd_binding.get("tier")) or {}).get("model")
check("prd.author 해석 모델 = gpt-6-sol",
      (codex_rt.get("models", {}).get(prd_model_alias) or {}).get("id") == "gpt-6-sol",
      repr(prd_model_alias))
check("research.cross 가 research.market 을 verifies",
      "research.market" in (role_specs.get("research.cross") or {}).get("verifies", []))
check("idea.cross 가 idea.generate 를 verifies",
      "idea.generate" in (role_specs.get("idea.cross") or {}).get("verifies", []))
check("roadmap.review 가 roadmap.author·roadmap.split 을 verifies",
      {"roadmap.author", "roadmap.split"} <= set(
          (role_specs.get("roadmap.review") or {}).get("verifies", [])))

print("claude-only 프로파일 — 리뷰·검증 노드는 T1 유지")
for role in ("research.verify", "roadmap.review"):
    value = bindings.get("claude-only", {}).get(role) or {}
    check(f"claude-only.{role} = claude/T1",
          value.get("runtime") == "claude" and value.get("tier") == "T1", repr(value))

print("스킬")
skill_path = os.path.join(ROOT, "skills", "private-roadmap", "SKILL.md")
check("skills/private-roadmap/SKILL.md 존재", os.path.exists(skill_path))
body = open(skill_path, encoding="utf-8").read() if os.path.exists(skill_path) else ""
block = h.frontmatter(skill_path) if body else ""
check("frontmatter name = private-roadmap", h.fm_value(block, "name") == "private-roadmap")
check("frontmatter user-invocable = true", h.fm_value(block, "user-invocable") == "true")
check("frontmatter requires = L2 (A‖B 병렬 스폰)", h.fm_value(block, "requires") == "L2")
declared = set(h.fm_list(block, "roles")) if block else set()
check("frontmatter roles 가 흐름의 role 전부를 선언", SKILL_ROLES <= declared,
      f"누락: {sorted(SKILL_ROLES - declared)}")
for phrase, why in [
    ("신규 아이디어", "경쟁사·고객·로드맵 외 신규 아이디어 제시"),
    ("게이트 ①", "로드맵 승인 사용자 게이트"),
    ("게이트 ②", "과제 확정 사용자 게이트"),
    ("최대 2회", "루프 종료 조건"),
    ("/private-feature", "확정 PRD 를 설계 단계로 넘기는 연결"),
]:
    check(f"본문에 '{phrase}' — {why}", phrase in body)
for category in ("fact", "priority", "boundary", "policy"):
    check(f"지적 유형별 루프백 '{category}' 정의", f"`{category}`" in body)
check("VOC(Metabase) 소스를 쓰지 않는다", "metabase" not in body.lower())

print("레지스트리")
skills_readme = open(os.path.join(ROOT, "skills", "README.md"), encoding="utf-8").read()
check("skills/README.md 에 /private-roadmap 행", "`/private-roadmap`" in skills_readme)
agents_readme = open(os.path.join(ROOT, "agents", "README.md"), encoding="utf-8").read()
for agent in sorted(set(NEW_ROLES.values())):
    check(f"agents/README.md 에 {agent} 행", f"`{agent}`" in agents_readme)

print("lint")
proc = subprocess.run([sys.executable, os.path.join(ROOT, "bin", "harness"), "lint"],
                      cwd=ROOT, capture_output=True, text=True)
check("harness lint exit 0", proc.returncode == 0, proc.stdout[-800:] + proc.stderr[-400:])
check("harness lint 경고 0", "경고 0" in proc.stdout, proc.stdout[-400:])

print()
if failures:
    print(f"실패 {len(failures)}건")
    sys.exit(1)
print("전부 통과")
