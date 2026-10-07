#!/usr/bin/env python3
"""런타임 페일오버가 교차 리뷰 불변식을 우회하지 못하게 하는지 검증.

`harness lint` 는 **정적 설정**만 본다. 노드가 실행 중 소진으로 다른 런타임으로 넘어가면
검증자와 피검증자가 같은 런타임이 될 수 있다 — 그러면 같은 맹점을 공유한다.
그 상태를 실행 시점에 잡아야 한다.

실행: python3 tests/test_cross_review_runtime.py
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile

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
d = load_module("orchestration/runner/dispatch.py", "harness_dispatch")

failures = []
TMP = tempfile.mkdtemp(prefix="harness-xreview-")
h.RUNS = os.path.join(TMP, "runs")
os.makedirs(h.RUNS, exist_ok=True)
roles = h.load("roles.json")


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        failures.append(name)
        print(f"  FAIL {name}" + (f" — {detail}" if detail else ""))


def quiet(fn, *args, **kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = fn(*args, **kwargs)
    return result, buf.getvalue()


GRAPH = {
    "id": "t-xr", "version": "1.0.0", "description": "교차 리뷰 테스트",
    "requires": "L1", "degrade_to": "L1",
    "nodes": [
        {"id": "impl", "skill": "inline", "role": "implement.be", "runtime": None,
         "tier": None, "requires": "L1", "inputs": [], "output_contract": None,
         "gate": None, "retry": {"max": 0, "on": []}, "on_failure": "halt",
         "timeout_sec": 60, "prompt": "구현한다."},
        {"id": "rev", "skill": "inline", "role": "review.code", "runtime": None,
         "tier": None, "requires": "L0", "inputs": ["impl"], "output_contract": None,
         "gate": None, "retry": {"max": 0, "on": []}, "on_failure": "halt",
         "timeout_sec": 60, "prompt": "리뷰한다."},
    ],
}
GP = os.path.join(TMP, "g.json")
json.dump(GRAPH, open(GP, "w"), ensure_ascii=False)


def state_with(impl_runtime, run_id):
    """impl 이 impl_runtime 으로 **실제 실행됐다**고 기록된 상태."""
    st = {"run_id": run_id, "graph": GP, "profile": "cross-review", "level": "L2",
          "objective": "x", "created_at": h.now_iso(), "nodes": {}}
    for n in GRAPH["nodes"]:
        st["nodes"][n["id"]] = {"status": "pending", "attempts": 0, "gate": None,
                                "degraded": None}
    st["nodes"]["impl"]["status"] = "completed"
    st["nodes"]["impl"]["runtime_used"] = impl_runtime
    rd = h.run_dir(run_id)
    if os.path.isdir(rd):
        shutil.rmtree(rd)
    os.makedirs(os.path.join(rd, "impl"), exist_ok=True)
    open(os.path.join(rd, "impl", "result.json"), "w").write('{"status":"done"}')
    h.save_state(st)
    return st


print("── 정적 설정 확인 ──")

check("review.code 가 implement.be 를 검증 선언",
      "implement.be" in (roles["roles"]["review.code"].get("verifies") or []),
      str(roles["roles"]["review.code"].get("verifies")))
static_impl = h.resolve_routing(roles, "implement.be", None, "cross-review")["runtime"]
static_rev = h.resolve_routing(roles, "review.code", None, "cross-review")["runtime"]
check("정적 바인딩은 교차", static_impl != static_rev, f"{static_impl} vs {static_rev}")

print("── 페일오버 없음 (정상 경로) ──")

st = state_with(static_impl, "xr-ok")
spec = h.build_node_spec(st, GRAPH, roles, "rev")
check("금지 런타임에 피검증자 런타임이 담긴다",
      spec.get("_forbidden_runtimes") == [static_impl], str(spec.get("_forbidden_runtimes")))
check("리뷰어 런타임은 그대로", spec["runtime"] == static_rev, spec["runtime"])

print("── 페일오버로 같은 런타임이 된 경우 ──")

# impl 이 소진으로 리뷰어와 같은 런타임으로 넘어갔다.
st = state_with(static_rev, "xr-clash")
spec = h.build_node_spec(st, GRAPH, roles, "rev")
check("충돌 감지 — 런타임이 재배정된다", spec["runtime"] != static_rev,
      f"{spec['runtime']} (피검증자 {static_rev})")
check("재배정 사실이 스펙에 기록", bool(spec.get("_rerouted")), str(spec.get("_rerouted")))
check("재배정된 런타임에 어댑터가 있다", spec["runtime"] in a.load_adapters(),
      spec["runtime"])
check("모델도 그 런타임 것으로 갱신", spec.get("model") is not None, str(spec.get("model")))

print("── 대체 런타임이 없으면 차단 ──")

# 피검증자들이 양쪽 런타임을 다 써버린 경우 (일부는 원래, 일부는 페일오버).
GRAPH2 = json.loads(json.dumps(GRAPH))
GRAPH2["nodes"].insert(1, {
    "id": "impl2", "skill": "inline", "role": "implement.fe", "runtime": None,
    "tier": None, "requires": "L1", "inputs": [], "output_contract": None,
    "gate": None, "retry": {"max": 0, "on": []}, "on_failure": "halt",
    "timeout_sec": 60, "prompt": "구현한다."})
GRAPH2["nodes"][-1]["inputs"] = ["impl", "impl2"]
GP2 = os.path.join(TMP, "g2.json")
json.dump(GRAPH2, open(GP2, "w"), ensure_ascii=False)

st = {"run_id": "xr-block", "graph": GP2, "profile": "cross-review", "level": "L2",
      "objective": "x", "created_at": h.now_iso(), "nodes": {}}
for n in GRAPH2["nodes"]:
    st["nodes"][n["id"]] = {"status": "pending", "attempts": 0, "gate": None,
                            "degraded": None}
for nid, rt in (("impl", "claude"), ("impl2", "codex")):
    st["nodes"][nid]["status"] = "completed"
    st["nodes"][nid]["runtime_used"] = rt
rd = h.run_dir("xr-block")
if os.path.isdir(rd):
    shutil.rmtree(rd)
for nid in ("impl", "impl2"):
    os.makedirs(os.path.join(rd, nid), exist_ok=True)
    open(os.path.join(rd, nid, "result.json"), "w").write('{"status":"done"}')
h.save_state(st)

spec = h.build_node_spec(st, GRAPH2, roles, "rev")
check("금지 런타임 2개", set(spec.get("_forbidden_runtimes") or []) == {"claude", "codex"},
      str(spec.get("_forbidden_runtimes")))
check("대체 불가가 스펙에 표시", spec.get("_cross_review_blocked") is True,
      str(spec.get("_cross_review_blocked")))

h.errors.clear()
rc, out = quiet(h.dispatch_ready, st, GRAPH2, roles, dry_run=True)
# 조용히 같은 런타임으로 돌리면 리뷰가 작성자와 같은 맹점을 공유한다 — 사람이 정해야 한다.
check("차단 시 디스패치하지 않는다", rc == 1, f"{rc} / {out[:200]}")
check("사유를 보고", any("맹점" in e or "교차" in e for e in h.errors), str(h.errors))
h.errors.clear()

print("── 페일오버가 금지 런타임으로 넘어가지 않는다 ──")

A_SRC = """
id = "src"
base = ["fake-src"]
prompt_delivery = "stdin"
result = "stdout_envelope"
envelope_result_key = "result"
[flags]
model = ["-m", "{value}"]
[access]
read-only = { model = "ro" }
workspace-write = { model = "rw" }
full = { model = "full" }
[failover]
fallback_to = "dst"
fallback_model = "dm"
exhaustion_patterns = ["usage limit"]
"""
A_DST = """
id = "dst"
base = ["fake-dst"]
prompt_delivery = "stdin"
result = "stdout_envelope"
envelope_result_key = "result"
[flags]
model = ["-m", "{value}"]
[access]
read-only = { model = "ro" }
workspace-write = { model = "rw" }
full = { model = "full" }
"""

import stat


def write_exec(path, body):
    open(path, "w").write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


binp = os.path.join(TMP, "bin")
os.makedirs(binp, exist_ok=True)
write_exec(os.path.join(binp, "fake-src"), """#!/bin/sh
cat > /dev/null
echo 'usage limit reached' >&2
exit 1
""")
write_exec(os.path.join(binp, "fake-dst"), """#!/bin/sh
cat > /dev/null
echo '{"result": "{\\"via\\": \\"dst\\"}"}'
""")
os.environ["PATH"] = binp + os.pathsep + os.environ["PATH"]

ad = os.path.join(TMP, "ad")
os.makedirs(ad, exist_ok=True)
open(os.path.join(ad, "src.toml"), "w").write(A_SRC)
open(os.path.join(ad, "dst.toml"), "w").write(A_DST)
ads = a.load_adapters(ad)
outdir = os.path.join(TMP, "out")
os.makedirs(outdir, exist_ok=True)

base_spec = {"id": "n", "runtime": "src", "model": "m", "prompt": "가라",
             "agent_file": None, "upstream": [], "contract_file": None,
             "cwd": TMP, "timeout_sec": 30}

r = d.run_node(dict(base_spec, id="f-free"), ads, outdir, {})
check("금지 목록 없으면 정상 failover", r["status"] == "ok" and r["runtime"] == "dst",
      json.dumps(r, ensure_ascii=False)[:200])

r = d.run_node(dict(base_spec, id="f-blocked", _forbidden_runtimes=["dst"]),
               ads, outdir, {})
check("금지 런타임으로는 failover 하지 않는다", r["status"] != "ok", str(r.get("status")))
check("전환 이력이 없다", not r.get("failover"), str(r.get("failover")))
check("차단 사유 기록", "교차" in str(r.get("failover_blocked") or ""),
      str(r.get("failover_blocked")))

shutil.rmtree(TMP, ignore_errors=True)
print()
if failures:
    print(f"실패 {len(failures)}건: {failures}")
    sys.exit(1)
print("전부 통과")
