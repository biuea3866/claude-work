#!/usr/bin/env python3
"""runtime budget failover 테스트 — codex 주간 사용량 임계 초과 시 claude 전환.

실행: python3 tests/test_runtime_budget.py
표준 라이브러리만 사용한다 (하네스는 pytest 의존을 갖지 않는다).
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_harness():
    path = os.path.join(ROOT, "bin", "harness")
    spec = importlib.util.spec_from_loader(
        "harness_cli", importlib.machinery.SourceFileLoader("harness_cli", path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


h = load_harness()

failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        failures.append(name)
        print(f"  FAIL {name}" + (f" — {detail}" if detail else ""))


def rate_limit_line(percent, window_minutes=10080, resets_at=1786167550, secondary=None):
    payload = {
        "type": "token_count",
        "info": {"total_token_usage": {"total_tokens": 1}},
        "rate_limits": {
            "limit_id": "codex",
            "primary": {"used_percent": percent, "window_minutes": window_minutes,
                        "resets_at": resets_at},
            "secondary": secondary,
            "plan_type": "plus",
        },
    }
    return json.dumps({"timestamp": "2026-08-14T00:00:00.000Z", "type": "event_msg",
                       "payload": payload})


def write_session(dirpath, name, lines, mtime=None):
    os.makedirs(dirpath, exist_ok=True)
    path = os.path.join(dirpath, name)
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    if mtime:
        os.utime(path, (mtime, mtime))
    return path


# ── 1. 사용량 리더 ────────────────────────────────────────────────────────────
print("codex_weekly_usage")

with tempfile.TemporaryDirectory() as tmp:
    sessions = os.path.join(tmp, "sessions", "2026", "08", "14")
    write_session(sessions, "rollout-old.jsonl", [rate_limit_line(11.0)], mtime=1_700_000_000)
    write_session(sessions, "rollout-new.jsonl",
                  [rate_limit_line(40.0), rate_limit_line(83.5)], mtime=1_800_000_000)

    usage = h.codex_weekly_usage(os.path.join(tmp, "sessions"))
    check("가장 최근 세션 파일의 마지막 스냅샷을 읽는다", usage and usage["percent"] == 83.5,
          f"got {usage}")
    check("주간 창(window_minutes=10080)을 식별한다", usage and usage["window_minutes"] == 10080,
          f"got {usage}")
    check("리셋 시각을 함께 반환한다", usage and usage["resets_at"] == 1786167550, f"got {usage}")

with tempfile.TemporaryDirectory() as tmp:
    sessions = os.path.join(tmp, "sessions")
    # primary=5시간 창, secondary=주간 창인 플랜
    line = rate_limit_line(95.0, window_minutes=300,
                           secondary={"used_percent": 61.0, "window_minutes": 10080,
                                      "resets_at": 1786167550})
    write_session(sessions, "rollout-a.jsonl", [line])
    usage = h.codex_weekly_usage(sessions)
    check("primary/secondary 중 주간 창을 고른다", usage and usage["percent"] == 61.0, f"got {usage}")

with tempfile.TemporaryDirectory() as tmp:
    check("세션 로그가 없으면 None", h.codex_weekly_usage(os.path.join(tmp, "nope")) is None)
    sessions = os.path.join(tmp, "sessions")
    write_session(sessions, "rollout-b.jsonl", ['{"type":"event_msg","payload":{"type":"agent_message"}}'])
    check("rate_limits 이벤트가 없으면 None", h.codex_weekly_usage(sessions) is None)

with tempfile.TemporaryDirectory() as tmp:
    sessions = os.path.join(tmp, "sessions")
    # 마지막 호출이 리셋 시각보다 오래됐다 — 그 사이 창이 새로 열렸으므로 수치는 무효
    write_session(sessions, "rollout-c.jsonl", [rate_limit_line(88.0, resets_at=1_000_000_000)])
    usage = h.codex_weekly_usage(sessions)
    check("리셋 시각이 지난 스냅샷은 stale 로 표시한다", usage and usage.get("stale") is True,
          f"got {usage}")

os.environ["HARNESS_CODEX_USAGE_PERCENT"] = "77"
check("환경변수 override 를 우선한다",
      (h.runtime_usage("codex") or {}).get("percent") == 77.0)
del os.environ["HARNESS_CODEX_USAGE_PERCENT"]


# ── 2. 예산 정책 ──────────────────────────────────────────────────────────────
print("budget_policy")

roles = h.load("roles.json")
policy = h.budget_policy(roles, "codex")
check("roles.json 에 codex 예산 정책이 있다", bool(policy), f"got {policy}")
check("임계는 주간 80%", policy and policy.get("threshold_percent") == 80, f"got {policy}")
check("fallback 은 claude-only 프로파일",
      policy and policy.get("fallback_profile") == "claude-only", f"got {policy}")
check("fallback 프로파일이 bindings 에 실재한다",
      policy and policy["fallback_profile"] in roles.get("bindings", {}))
check("claude 런타임에는 예산 정책이 없다", h.budget_policy(roles, "claude") is None)


# ── 3. 게이트 상태 기계 ───────────────────────────────────────────────────────
print("check_budget")

GRAPH_NODES = {
    "design-be": {"id": "design-be", "role": "design.be", "requires": "L1", "inputs": []},
    "impl-be": {"id": "impl-be", "role": "implement.be", "requires": "L1", "inputs": []},
}


def fresh_state(profile="cross-review"):
    return {"run_id": "test-run", "graph": "orchestration/private-feature.json",
            "profile": profile, "level": "L2", "nodes": {
                "design-be": {"status": "pending", "attempts": 0},
                "impl-be": {"status": "pending", "attempts": 0}}}


def silent(fn, *a, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = fn(*a, **kw)
    return result, buf.getvalue()


with tempfile.TemporaryDirectory() as tmp:
    h.RUNS = tmp  # journal/state 쓰기를 임시 디렉토리로

    os.environ["HARNESS_CODEX_USAGE_PERCENT"] = "85"
    state = fresh_state()
    blocked, _ = silent(h.check_budget, state, roles, ["design-be", "impl-be"], GRAPH_NODES)
    check("임계 초과 + codex 노드 대기 → 게이트가 열린다", blocked is True)
    check("게이트 상태는 pending", state.get("budget_gate", {}).get("status") == "pending",
          f"got {state.get('budget_gate')}")
    check("게이트에 측정값이 기록된다", state.get("budget_gate", {}).get("percent") == 85.0)
    check("승인 전에는 프로파일이 바뀌지 않는다", state["profile"] == "cross-review")

    # codex 로 가는 ready 노드가 없으면 임계를 넘어도 막지 않는다
    state2 = fresh_state()
    blocked2, _ = silent(h.check_budget, state2, roles, ["impl-be"], GRAPH_NODES)
    check("ready 노드가 전부 claude 면 게이트를 열지 않는다", blocked2 is False,
          f"got {state2.get('budget_gate')}")

    # stale 스냅샷으로는 전환을 걸지 않는다 (창이 이미 리셋됐을 수 있다)
    stale_dir = os.path.join(tmp, "stale-sessions")
    write_session(stale_dir, "rollout-stale.jsonl",
                  [rate_limit_line(88.0, resets_at=1_000_000_000)])
    del os.environ["HARNESS_CODEX_USAGE_PERCENT"]
    os.environ["HARNESS_CODEX_SESSIONS_DIR"] = stale_dir
    state_stale = fresh_state()
    blocked_stale, _ = silent(h.check_budget, state_stale, roles, ["design-be"], GRAPH_NODES)
    check("stale 사용량으로는 게이트를 열지 않는다", blocked_stale is False,
          f"got {state_stale.get('budget_gate')}")
    del os.environ["HARNESS_CODEX_SESSIONS_DIR"]

    os.environ["HARNESS_CODEX_USAGE_PERCENT"] = "42"
    state3 = fresh_state()
    blocked3, _ = silent(h.check_budget, state3, roles, ["design-be"], GRAPH_NODES)
    check("임계 미만이면 게이트를 열지 않는다", blocked3 is False)

    # 승인 → 프로파일 전환
    os.environ["HARNESS_CODEX_USAGE_PERCENT"] = "85"
    state4 = fresh_state()
    silent(h.check_budget, state4, roles, ["design-be"], GRAPH_NODES)
    silent(h.resolve_budget_gate, state4, roles, approve=True)
    check("승인하면 프로파일이 claude-only 로 전환된다", state4["profile"] == "claude-only")
    check("승인 후 게이트는 approved", state4["budget_gate"]["status"] == "approved")
    routing = h.resolve_routing(roles, "design.be", GRAPH_NODES["design-be"], state4["profile"])
    check("전환 후 design.be 는 claude 로 해석된다", routing["runtime"] == "claude",
          f"got {routing}")
    blocked4, _ = silent(h.check_budget, state4, roles, ["design-be"], GRAPH_NODES)
    check("전환 후에는 다시 막지 않는다", blocked4 is False)

    # 반려 → 같은 사용량에서는 다시 묻지 않는다
    state5 = fresh_state()
    silent(h.check_budget, state5, roles, ["design-be"], GRAPH_NODES)
    silent(h.resolve_budget_gate, state5, roles, approve=False)
    check("반려하면 프로파일은 유지된다", state5["profile"] == "cross-review")
    blocked5, _ = silent(h.check_budget, state5, roles, ["design-be"], GRAPH_NODES)
    check("반려 후 같은 사용량에서는 재질문하지 않는다", blocked5 is False)
    os.environ["HARNESS_CODEX_USAGE_PERCENT"] = "91"
    blocked6, _ = silent(h.check_budget, state5, roles, ["design-be"], GRAPH_NODES)
    check("사용량이 재질문 폭만큼 더 오르면 다시 묻는다", blocked6 is True)

    # print_next 는 게이트가 걸린 동안 디스패치를 막는다
    os.environ["HARNESS_CODEX_USAGE_PERCENT"] = "85"
    state7 = fresh_state()
    graph = {"id": "test", "nodes": list(GRAPH_NODES.values())}
    _, out = silent(h.print_next, state7, graph, roles)
    check("게이트 중에는 invoke 를 출력하지 않는다", "invoke" not in out, out[:200])
    check("게이트 안내와 승인 커맨드를 출력한다",
          "harness run budget --approve" in out, out[:300])

    del os.environ["HARNESS_CODEX_USAGE_PERCENT"]

print()
if failures:
    print(f"실패 {len(failures)}건: {', '.join(failures)}")
    sys.exit(1)
print("전부 통과")
