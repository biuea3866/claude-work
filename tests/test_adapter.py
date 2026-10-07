#!/usr/bin/env python3
"""벤더 어댑터 테스트 — argv 조립 · 소진 감지 · failover 변환.

실행: python3 tests/test_adapter.py
표준 라이브러리만 사용한다 (하네스는 pytest 의존을 갖지 않는다).
"""
import importlib.machinery
import importlib.util
import os
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


a = load_module("orchestration/runner/adapter.py", "harness_adapter")

failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        failures.append(name)
        print(f"  FAIL {name}" + (f" — {detail}" if detail else ""))


def expect_fail(name, fn, needle=""):
    """fn 이 AdapterError 를 던지는지 본다. 메시지에 needle 이 있어야 한다."""
    try:
        fn()
    except a.AdapterError as e:
        check(name, needle in str(e), f"메시지에 '{needle}' 없음: {e}")
        return
    except Exception as e:  # noqa: BLE001
        check(name, False, f"AdapterError 가 아닌 예외: {type(e).__name__}: {e}")
        return
    check(name, False, "예외가 나지 않았다")


def write_adapters(tmp, files):
    d = os.path.join(tmp, "adapters")
    os.makedirs(d, exist_ok=True)
    for name, body in files.items():
        with open(os.path.join(d, name), "w") as f:
            f.write(body)
    return d


MINIMAL = """
id = "x"
base = ["x-cli"]
prompt_delivery = "stdin"
result = "stdout_envelope"
[flags]
model = ["-m", "{value}"]
"""

print("── 어댑터 로드 ──")

with tempfile.TemporaryDirectory() as tmp:
    d = write_adapters(tmp, {"x.toml": MINIMAL})
    adapters = a.load_adapters(d)
    check("최소 어댑터 로드", set(adapters) == {"x"}, str(list(adapters)))

with tempfile.TemporaryDirectory() as tmp:
    d = write_adapters(tmp, {"bad.toml": 'id = "b"\nbase = ["b"]\n'})
    expect_fail("필수 키 누락 시 실패", lambda: a.load_adapters(d), "prompt_delivery")

with tempfile.TemporaryDirectory() as tmp:
    d = write_adapters(tmp, {"bad.toml": MINIMAL.replace('"stdin"', '"telepathy"')})
    expect_fail("prompt_delivery 값 검증", lambda: a.load_adapters(d), "prompt_delivery")

with tempfile.TemporaryDirectory() as tmp:
    d = write_adapters(tmp, {"bad.toml": MINIMAL.replace('"stdout_envelope"', '"vibes"')})
    expect_fail("result 값 검증", lambda: a.load_adapters(d), "result")

with tempfile.TemporaryDirectory() as tmp:
    d = write_adapters(tmp, {})
    expect_fail("어댑터 0개면 실패", lambda: a.load_adapters(d), "어댑터가 없습니다")

with tempfile.TemporaryDirectory() as tmp:
    body = MINIMAL + '\n[failover]\nfallback_to = "nope"\n'
    d = write_adapters(tmp, {"x.toml": body})
    expect_fail("없는 벤더로 failover 선언 시 실패", lambda: a.load_adapters(d), "nope")

with tempfile.TemporaryDirectory() as tmp:
    body = MINIMAL + '\n[failover]\nfallback_to = "x"\n'
    d = write_adapters(tmp, {"x.toml": body})
    expect_fail("자기 자신으로 failover 시 실패", lambda: a.load_adapters(d), "자기 자신")

print("── argv 조립 ──")

FULL = """
id = "y"
base = ["y-cli", "--json"]
prompt_delivery = "argv"
result = "out_file"
[defaults]
sandbox = "read-only"
[flags]
model = ["-m", "{value}"]
tools = ["--allowed", "{csv}"]
role_file = ["--role", "{root_path}"]
sandbox = ["-s", "{value}"]
[runtime]
out_file = ["-o", "{path}"]
cwd = ["-C", "{path}"]
"""

with tempfile.TemporaryDirectory() as tmp:
    d = write_adapters(tmp, {"y.toml": FULL})
    ad = a.load_adapters(d)["y"]

    cmd = a.build_command({"id": "n1", "runtime": "y", "model": "m1"}, ad,
                          out_path="/o/n1.json", cwd="/w", root=ROOT)
    check("base 가 앞에 온다", cmd[:2] == ["y-cli", "--json"], str(cmd))
    check("runtime 슬롯 채움", "-o" in cmd and "/o/n1.json" in cmd, str(cmd))
    check("cwd 슬롯 채움", "-C" in cmd and "/w" in cmd, str(cmd))
    check("노드 플래그 반영", "-m" in cmd and "m1" in cmd, str(cmd))
    check("defaults 적용", "-s" in cmd and "read-only" in cmd, str(cmd))

    cmd = a.build_command({"id": "n2", "runtime": "y", "model": "m", "sandbox": "rw"}, ad,
                          out_path="/o/x", cwd="/w", root=ROOT)
    check("노드가 defaults 를 이긴다", "rw" in cmd and "read-only" not in cmd, str(cmd))

    cmd = a.build_command({"id": "n3", "runtime": "y", "tools": ["Read", "Grep"]}, ad,
                          out_path="/o/x", cwd="/w", root=ROOT)
    check("{csv} 치환", "Read,Grep" in cmd, str(cmd))

    expect_fail("미지원 키는 실행 전에 실패",
                lambda: a.build_command({"id": "n4", "runtime": "y", "mcp_config": "z"}, ad,
                                        out_path="/o/x", cwd="/w", root=ROOT),
                "지원하지 않습니다")

    expect_fail("{root_path} 파일 부재 시 실패",
                lambda: a.build_command({"id": "n5", "runtime": "y",
                                         "role_file": "agents/no-such-agent.md"}, ad,
                                        out_path="/o/x", cwd="/w", root=ROOT),
                "파일 없음")

    cmd = a.build_command({"id": "n6", "runtime": "y", "role_file": "roles.json"}, ad,
                          out_path="/o/x", cwd="/w", root=ROOT)
    check("{root_path} 는 하네스 루트 기준", os.path.join(ROOT, "roles.json") in cmd, str(cmd))

    expect_fail("{csv} 에 리스트가 아닌 값",
                lambda: a.build_command({"id": "n7", "runtime": "y", "tools": "Read"}, ad,
                                        out_path="/o/x", cwd="/w", root=ROOT),
                "리스트")

print("── 소진 감지 ──")

FO = """
id = "p"
base = ["p"]
prompt_delivery = "stdin"
result = "stdout_envelope"
[flags]
model = ["-m", "{value}"]
permission_mode = ["--pm", "{value}"]
[failover]
fallback_to = "q"
fallback_model = "qm"
exhaustion_patterns = ["usage limit reached", "\\"api_error_status\\"\\\\s*:\\\\s*429", "is at capacity"]
[failover.translate.permission_mode]
dontAsk = { key = "sandbox", value = "read-only" }
"""
Q = """
id = "q"
base = ["q"]
prompt_delivery = "stdin"
result = "out_file"
[flags]
model = ["-m", "{value}"]
sandbox = ["-s", "{value}"]
"""

with tempfile.TemporaryDirectory() as tmp:
    d = write_adapters(tmp, {"p.toml": FO, "q.toml": Q})
    ads = a.load_adapters(d)
    p, q = ads["p"], ads["q"]

    check("대소문자 무시", a.detect_exhaustion(p, "USAGE LIMIT REACHED") is not None)
    # 2026-08-21 UND-13~22 관측: 세션 한도는 키가 api_error_status 다.
    check("api_error_status 429 감지",
          a.detect_exhaustion(p, '{"api_error_status": 429}') is not None)
    # 2026-08-21 UND-21 관측: codex 는 용량 부족을 "at capacity" 로 알린다.
    check("at capacity 감지",
          a.detect_exhaustion(p, "Selected model is at capacity") is not None)
    check("무관한 오류는 미감지", a.detect_exhaustion(p, "compile error") is None)
    check("failover 선언 없으면 미감지", a.detect_exhaustion(q, "usage limit reached") is None)

    print("── failover 변환 ──")
    node = {"id": "n", "runtime": "p", "model": "pm", "permission_mode": "dontAsk",
            "role": "review.code", "timeout_sec": 60}
    adapted, notes = a.adapt_node_for_failover(node, p, q)
    check("runtime 이 대상으로 바뀐다", adapted["runtime"] == "q", str(adapted))
    check("모델이 fallback_model 로", adapted["model"] == "qm", str(adapted))
    check("translate 규칙 적용", adapted.get("sandbox") == "read-only", str(adapted))
    check("예약 키는 보존", adapted.get("role") == "review.code" and adapted["timeout_sec"] == 60,
          str(adapted))
    check("변환 사실이 기록된다", any("permission_mode" in n for n in notes), str(notes))

    node2 = {"id": "n", "runtime": "p", "model": "pm", "output_schema": "s.json"}
    adapted2, notes2 = a.adapt_node_for_failover(node2, p, q)
    check("미지원 키는 제거된다", "output_schema" not in adapted2, str(adapted2))
    # 조용히 사라지면 산출물 품질이 떨어진 이유를 알 수 없다.
    check("제거 사실이 기록된다", any("output_schema" in n and "제거" in n for n in notes2),
          str(notes2))

print("── 실제 하네스 어댑터 ──")

real = a.load_adapters()
check("claude·codex 어댑터 실재", {"claude", "codex"} <= set(real), str(list(real)))
for name, ad in real.items():
    fo = ad.get("failover", {})
    check(f"{name}: failover 선언", bool(fo.get("fallback_to")), str(fo))
    check(f"{name}: 소진 패턴 존재", len(fo.get("exhaustion_patterns", [])) > 0)

print()
if failures:
    print(f"실패 {len(failures)}건: {failures}")
    sys.exit(1)
print("전부 통과")
