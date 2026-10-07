#!/usr/bin/env python3
"""디스패처 테스트 — 프롬프트 조립 · 실행 · failover · wave 병렬.

실행: python3 tests/test_dispatch.py
표준 라이브러리만 사용한다. 실제 LLM 을 부르지 않는다 — 가짜 CLI 스크립트를 PATH 에 올린다.
"""
import importlib.machinery
import importlib.util
import json
import os
import stat
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_module(rel, name):
    path = os.path.join(ROOT, rel)
    spec = importlib.util.spec_from_loader(
        name, importlib.machinery.SourceFileLoader(name, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


a = load_module("orchestration/runner/adapter.py", "harness_adapter")
d = load_module("orchestration/runner/dispatch.py", "harness_dispatch")

failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        failures.append(name)
        print(f"  FAIL {name}" + (f" — {detail}" if detail else ""))


def expect_fail(name, fn, needle=""):
    try:
        fn()
    except d.DispatchError as e:
        check(name, needle in str(e), f"메시지에 '{needle}' 없음: {e}")
        return
    except Exception as e:  # noqa: BLE001
        check(name, False, f"DispatchError 가 아닌 예외: {type(e).__name__}: {e}")
        return
    check(name, False, "예외가 나지 않았다")


def write_exec(path, body):
    with open(path, "w") as f:
        f.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


# ─────────────────────────────────────────────────────────── 프롬프트 조립

print("── 프롬프트 조립 ──")

with tempfile.TemporaryDirectory() as tmp:
    agent = os.path.join(tmp, "persona.md")
    open(agent, "w").write("나는 시니어 BE 다.")
    up = os.path.join(tmp, "prd.json")
    open(up, "w").write('{"ok": true}')
    contract = os.path.join(tmp, "c.schema.json")
    open(contract, "w").write('{"type": "object"}')

    spec = {"id": "design-be", "role": "design.be", "agent_file": agent,
            "prompt": "PRD 를 읽고 TDD 를 쓴다.",
            "upstream": [("prd", up)], "contract_file": contract}
    text = d.build_prompt(spec, {})
    check("역할 섹션", "# 역할" in text and "시니어 BE" in text)
    check("작업 섹션", "# 작업" in text and "TDD" in text)
    check("입력 섹션에 경로", "# 입력" in text and up in text)
    # 없는 산출물을 근거로 쓰라고 하면 노드가 추측으로 채운다.
    check("추측 금지 문구", "추측하지" in text)
    check("출력 계약 섹션", "# 출력 계약" in text and '"type": "object"' in text)

    spec_noup = dict(spec, upstream=[])
    check("업스트림 없으면 입력 섹션 없음", "# 입력" not in d.build_prompt(spec_noup, {}))

    # 실행 전 전수 검증 — 없는 경로는 실패가 아니라 침묵이 되어 근거 없는 산출물을 만든다.
    spec_missing = dict(spec, upstream=[("prd", os.path.join(tmp, "no-such.json"))])
    expect_fail("업스트림 산출물 부재 시 실행 전 중단",
                lambda: d.build_prompt(spec_missing, {}), "업스트림 산출물이 없습니다")

    spec_agent = dict(spec, agent_file=os.path.join(tmp, "no-agent.md"))
    expect_fail("페르소나 파일 부재 시 중단",
                lambda: d.build_prompt(spec_agent, {}), "페르소나")

print("── 자리표시자 ──")

check("치환 성공", d.substitute("목표: {{objective}}", {"objective": "대여"}, "x")
      == "목표: 대여")
expect_fail("미치환 자리표시자는 실행 전 실패",
            lambda: d.substitute("{{a}} {{b}}", {"a": "1"}, "노드 n"), "b")

print("── JSON 추출 ──")

check("순수 JSON", d.extract_json_object('{"a":1}') == {"a": 1})
check("코드펜스", d.extract_json_object('```json\n{"a":2}\n```') == {"a": 2})
check("머리말", d.extract_json_object('설명입니다.\n{"a":3}') == {"a": 3})
check("JSON 없음", "_parse_error" in d.extract_json_object("그냥 산문"))
check("깨진 JSON", "_parse_error" in d.extract_json_object('{"a": }'))

# 실제 claude CLI 는 봉투 뒤에 비JSON 경고 줄을 섞어 내보낸다 (MCP 관련 stderr 누수).
REAL_NOISE = '{"is_error": false, "result": "{\\"ok\\": true}"}\nClient.listTools() called'
env = d.extract_json_object(REAL_NOISE)
check("봉투 뒤 비JSON 줄을 무시", env.get("is_error") is False, str(env)[:120])

# 잡음이 **JSON** 이면 탐욕 매칭이 봉투 밖까지 삼켜 파싱이 깨진다.
TWO_OBJECTS = '{"is_error": false, "result": "ok"}\n{"noise": 1}'
env = d.extract_json_object(TWO_OBJECTS)
check("뒤에 붙은 잡음 JSON 을 무시", env.get("result") == "ok", str(env)[:150])

# 앞에 붙는 경우도 있다 (경고가 먼저 나올 때).
NOISE_FIRST = '{"warn": 1}\n{"is_error": false, "result": "big enough payload here"}'
env = d.extract_json_object(NOISE_FIRST)
check("가장 큰 유효 객체를 고른다", env.get("result") == "big enough payload here",
      str(env)[:150])

print("── 봉투 오류 플래그 ──")

# claude 는 API 오류에도 exit 0 을 낸다 — is_error 를 안 보면 실패를 성공으로 오판한다.
CREDIT = '{"is_error": true, "result": "Credit balance is too low", "total_cost_usd": 0}'
env = d.extract_json_object(CREDIT)
check("is_error 플래그 노출", env.get("is_error") is True, str(env))

# ─────────────────────────────────────────────────────────── 실행

print("── 노드 실행 ──")

ENVELOPE_OK = """#!/bin/sh
cat > /dev/null
echo '{"result": "{\\"status\\": \\"done\\"}", "total_cost_usd": 0.25}'
"""
ENVELOPE_EXHAUSTED = """#!/bin/sh
cat > /dev/null
echo 'You have hit your session limit' >&2
exit 1
"""
OUTFILE_OK = """#!/bin/sh
out=""
while [ $# -gt 0 ]; do
  if [ "$1" = "-o" ]; then out="$2"; fi
  shift
done
echo '{"status": "done", "via": "outfile"}' > "$out"
"""
SLOW = """#!/bin/sh
cat > /dev/null
sleep 5
echo '{"result": "{}"}'
"""

A_ENV = """
id = "aenv"
base = ["fake-env"]
prompt_delivery = "stdin"
result = "stdout_envelope"
envelope_result_key = "result"
envelope_cost_key = "total_cost_usd"
[flags]
model = ["-m", "{value}"]
"""
A_OUT = """
id = "aout"
base = ["fake-out"]
prompt_delivery = "argv"
result = "out_file"
[flags]
model = ["-m", "{value}"]
[runtime]
out_file = ["-o", "{path}"]
"""


def adapters_with(tmp, extra=""):
    ad = os.path.join(tmp, "adapters")
    os.makedirs(ad, exist_ok=True)
    open(os.path.join(ad, "aenv.toml"), "w").write(A_ENV + extra)
    open(os.path.join(ad, "aout.toml"), "w").write(A_OUT)
    return a.load_adapters(ad)


with tempfile.TemporaryDirectory() as tmp:
    binp = os.path.join(tmp, "bin")
    os.makedirs(binp)
    write_exec(os.path.join(binp, "fake-env"), ENVELOPE_OK)
    write_exec(os.path.join(binp, "fake-out"), OUTFILE_OK)
    write_exec(os.path.join(binp, "fake-slow"), SLOW)
    os.environ["PATH"] = binp + os.pathsep + os.environ["PATH"]

    ads = adapters_with(tmp)
    outdir = os.path.join(tmp, "out")
    os.makedirs(outdir)

    spec = {"id": "n1", "runtime": "aenv", "model": "m", "prompt": "일해라",
            "agent_file": None, "upstream": [], "contract_file": None,
            "cwd": tmp, "timeout_sec": 30}
    r = d.run_node(spec, ads, outdir, {})
    check("봉투 런타임 성공", r["status"] == "ok", json.dumps(r, ensure_ascii=False))
    check("비용 회수", r.get("cost_usd") == 0.25, str(r.get("cost_usd")))
    saved = json.load(open(os.path.join(outdir, "n1", "result.json")))
    check("봉투 안 JSON 을 산출물로", saved == {"status": "done"}, str(saved))
    check("프롬프트 보존", os.path.isfile(os.path.join(outdir, "n1", "prompt.txt")))
    check("로그 보존", os.path.isfile(os.path.join(outdir, "n1", "node.log")))

    spec2 = dict(spec, id="n2", runtime="aout")
    r2 = d.run_node(spec2, ads, outdir, {})
    check("out_file 런타임 성공", r2["status"] == "ok", json.dumps(r2, ensure_ascii=False))
    saved2 = json.load(open(os.path.join(outdir, "n2", "result.json")))
    check("out_file 산출물", saved2.get("via") == "outfile", str(saved2))

    spec3 = dict(spec, id="n3", runtime="aenv")
    ads_missing = a.load_adapters(os.path.join(tmp, "adapters"))
    ads_missing["aenv"] = dict(ads_missing["aenv"], base=["definitely-not-a-real-cli"])
    r3 = d.run_node(spec3, ads_missing, outdir, {})
    check("CLI 부재는 failed", r3["status"] == "failed" and "찾을 수 없" in r3.get("error", ""),
          json.dumps(r3, ensure_ascii=False))

    spec4 = dict(spec, id="n4", timeout_sec=1)
    ads_slow = a.load_adapters(os.path.join(tmp, "adapters"))
    ads_slow["aenv"] = dict(ads_slow["aenv"], base=["fake-slow"])
    r4 = d.run_node(spec4, ads_slow, outdir, {})
    check("타임아웃 판정", r4["status"] == "timeout", json.dumps(r4, ensure_ascii=False))

    # 이전 시도의 산출물이 남아 있으면 실패를 성공으로 오판한다.
    stale_dir = os.path.join(outdir, "n5")
    os.makedirs(stale_dir, exist_ok=True)
    open(os.path.join(stale_dir, "result.json"), "w").write('{"stale": true}')
    spec5 = dict(spec, id="n5")
    ads_bad = a.load_adapters(os.path.join(tmp, "adapters"))
    ads_bad["aenv"] = dict(ads_bad["aenv"], base=["definitely-not-a-real-cli"])
    d.run_node(spec5, ads_bad, outdir, {})
    stale_path = os.path.join(stale_dir, "result.json")
    # 지워졌거나(조기 반환) 새 내용으로 덮였거나 — 어느 쪽이든 stale 이 남으면 안 된다.
    left = json.load(open(stale_path)) if os.path.isfile(stale_path) else {}
    check("이전 산출물을 성공으로 오판하지 않는다", left.get("stale") is not True, str(left))

print("── 어댑터 [env] ──")

ENVCHK = """#!/bin/sh
cat > /dev/null
if [ -n "$SHOULD_BE_GONE" ]; then
  echo '{"result": "{\\"leaked\\": true}"}'
else
  echo '{"result": "{\\"clean\\": true}"}'
fi
"""

with tempfile.TemporaryDirectory() as tmp:
    binp = os.path.join(tmp, "bin")
    os.makedirs(binp)
    write_exec(os.path.join(binp, "fake-env"), ENVCHK)
    write_exec(os.path.join(binp, "fake-out"), OUTFILE_OK)
    os.environ["PATH"] = binp + os.pathsep + os.environ["PATH"]
    os.environ["SHOULD_BE_GONE"] = "yes"

    # [env] 선언이 없으면 부모 환경이 그대로 전달된다.
    ads = adapters_with(tmp)
    outdir = os.path.join(tmp, "out")
    os.makedirs(outdir)
    spec = {"id": "e1", "runtime": "aenv", "model": "m", "prompt": "가라",
            "agent_file": None, "upstream": [], "contract_file": None,
            "cwd": tmp, "timeout_sec": 30}
    d.run_node(spec, ads, outdir, {})
    got = json.load(open(os.path.join(outdir, "e1", "result.json")))
    check("[env] 없으면 부모 환경 그대로", got.get("leaked") is True, str(got))

    # unset 선언이 있으면 그 변수를 지운 채 실행한다.
    ads2 = adapters_with(tmp, '\n[env]\nunset = ["SHOULD_BE_GONE"]\n')
    d.run_node(dict(spec, id="e2"), ads2, outdir, {})
    got = json.load(open(os.path.join(outdir, "e2", "result.json")))
    check("[env] unset 이 변수를 제거", got.get("clean") is True, str(got))
    check("부모 프로세스 환경은 그대로", os.environ.get("SHOULD_BE_GONE") == "yes")
    del os.environ["SHOULD_BE_GONE"]

print("── failover ──")

with tempfile.TemporaryDirectory() as tmp:
    binp = os.path.join(tmp, "bin")
    os.makedirs(binp)
    write_exec(os.path.join(binp, "fake-env"), ENVELOPE_EXHAUSTED)
    write_exec(os.path.join(binp, "fake-out"), OUTFILE_OK)
    os.environ["PATH"] = binp + os.pathsep + os.environ["PATH"]

    extra = """
[failover]
fallback_to = "aout"
fallback_model = "fm"
exhaustion_patterns = ["hit your (session|usage) limit"]
"""
    ads = adapters_with(tmp, extra)
    outdir = os.path.join(tmp, "out")
    os.makedirs(outdir)

    spec = {"id": "f1", "runtime": "aenv", "model": "m", "prompt": "일해라",
            "agent_file": None, "upstream": [], "contract_file": None,
            "cwd": tmp, "timeout_sec": 30}
    r = d.run_node(spec, ads, outdir, {})
    check("소진 시 대체 런타임으로 성공", r["status"] == "ok", json.dumps(r, ensure_ascii=False))
    check("전환 이력 기록", bool(r.get("failover")), str(r.get("failover")))
    check("요청 런타임 보존", r.get("runtime_requested") == "aenv", str(r))
    check("최종 런타임은 대체", r["runtime"] == "aout", str(r))

    r2 = d.run_node(dict(spec, id="f2"), ads, outdir, {}, failover=False)
    check("--no-failover 면 전환 없음", r2["status"] != "ok" and not r2.get("failover"),
          json.dumps(r2, ensure_ascii=False))

print("── wave 병렬 ──")

SLEEPY = """#!/bin/sh
cat > /dev/null
sleep 1
echo '{"result": "{\\"ok\\": true}"}'
"""

with tempfile.TemporaryDirectory() as tmp:
    binp = os.path.join(tmp, "bin")
    os.makedirs(binp)
    write_exec(os.path.join(binp, "fake-env"), SLEEPY)
    write_exec(os.path.join(binp, "fake-out"), OUTFILE_OK)
    os.environ["PATH"] = binp + os.pathsep + os.environ["PATH"]
    ads = adapters_with(tmp)
    outdir = os.path.join(tmp, "out")
    os.makedirs(outdir)

    specs = [{"id": f"w{i}", "runtime": "aenv", "model": "m", "prompt": "가라",
              "agent_file": None, "upstream": [], "contract_file": None,
              "cwd": tmp, "timeout_sec": 30} for i in range(4)]

    started = time.monotonic()
    results = d.run_wave(specs, ads, outdir, {}, max_parallel=4)
    elapsed = time.monotonic() - started
    check("전원 실행", len(results) == 4 and all(r["status"] == "ok" for r in results),
          str([r["status"] for r in results]))
    # 1초짜리 4개가 직렬이면 4초, 병렬이면 ~1초. 3초 미만이면 병렬이 실증된다.
    check("실제 병렬 실행", elapsed < 3.0, f"{elapsed:.1f}s — 직렬화 의심")

    plan = d.run_wave(specs, ads, outdir, {}, max_parallel=4, dry_run=True)
    check("dry-run 은 실행하지 않는다",
          all(r["status"] == "dry-run" for r in plan), str([r["status"] for r in plan]))

print()
if failures:
    print(f"실패 {len(failures)}건: {failures}")
    sys.exit(1)
print("전부 통과")
