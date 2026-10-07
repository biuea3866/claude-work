#!/usr/bin/env python3
"""tier 축이 '최상위 모델' 슬롯을 갖고, 교차 리뷰 게이트가 그 슬롯에 배정되는지 검증.

tier 는 '런타임 안의 성능 등급' 축이다. 신규 최상위 모델을 T1 전체(codex 7개 노드)를
건드리지 않고 일부 노드에만 시범 배치하려면 T1 위에 슬롯이 하나 필요하다.
lint 가 tier 값을 TIERS 로 화이트리스트하므로 슬롯이 없으면 바인딩 자체가 반려된다.

실행: python3 tests/test_tier_taxonomy.py
"""
import importlib.machinery
import importlib.util
import os
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

failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        failures.append(name)
        print(f"  FAIL {name}" + (f" — {detail}" if detail else ""))


print("tier 슬롯")
check("TIERS 에 최상위 슬롯 T0 가 있다", "T0" in h.TIERS, repr(h.TIERS))
check("T0 는 T1 보다 앞선다 (서열 = 선언 순서)",
      "T0" in h.TIERS and h.TIERS.index("T0") < h.TIERS.index("T1"), repr(h.TIERS))
check("_tier_doc 에 T0 의 의미가 적혀 있다",
      bool((roles.get("_tier_doc") or {}).get("T0")))

print("\n모든 런타임이 모든 tier 를 정의한다 (lint 불변식)")
for rt, spec in (roles.get("runtimes") or {}).items():
    for tier in h.TIERS:
        t = (spec.get("tiers") or {}).get(tier)
        check(f"{rt}.tiers.{tier} 정의됨", isinstance(t, dict) and "model" in t, repr(t))
        if isinstance(t, dict) and "model" in t:
            check(f"{rt}.tiers.{tier} 가 카탈로그의 모델을 가리킨다",
                  t["model"] in (spec.get("models") or {}), t["model"])

print("\ncodex 카탈로그")
astra = ((roles["runtimes"]["codex"].get("models") or {}).get("astra") or {})
check("codex.models.astra 등록됨", astra.get("id") == "gpt-6-astra", repr(astra))
check("astra 는 실호출로 검증됨(verified)", astra.get("verified") is True)

print("\n교차 리뷰 게이트 라우팅 (cross-review 프로파일)")
for role in ("review.code", "review.infra"):
    r = h.resolve_routing(roles, role, None, "cross-review")
    check(f"{role} → codex", (r or {}).get("runtime") == "codex", repr(r))
    check(f"{role} → gpt-6-astra", (r or {}).get("model") == "gpt-6-astra", repr(r))
    check(f"{role} → effort=high", (r or {}).get("effort") == "high", repr(r))

print("\n나머지 codex T1 노드는 그대로 sol 이다 (시범 배치 범위 격리)")
for role in ("architect", "design.be", "design.fe", "design.db", "plan.coordinate"):
    r = h.resolve_routing(roles, role, None, "cross-review")
    check(f"{role} → gpt-5.6-sol", (r or {}).get("model") == "gpt-5.6-sol", repr(r))

print("\nT0 바인딩이 lint 를 통과한다")
for rt in ("codex", "claude"):
    check(f"lint_binding_value({rt}/T0) 수락",
          h.lint_binding_value("test", {"runtime": rt, "tier": "T0"},
                               roles["runtimes"]) == (rt, "T0"))

print()
if failures:
    print(f"실패 {len(failures)}건: {', '.join(failures)}")
    sys.exit(1)
print("전부 통과")
