#!/usr/bin/env python3
"""상태 기계 + 디스패처 통합 테스트.

앞부분은 기존 done/fail 동작의 **회귀 방지 네트**다 (로직을 함수로 추출하기 전에 고정한다).
뒷부분은 신설 dispatch 경로를 검증한다.

실행: python3 tests/test_run_dispatch.py
"""
import importlib.machinery
import importlib.util
import io
import contextlib
import json
import os
import shutil
import stat
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

failures = []
TMP = tempfile.mkdtemp(prefix="harness-run-test-")
h.RUNS = os.path.join(TMP, "runs")
os.makedirs(h.RUNS, exist_ok=True)


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        failures.append(name)
        print(f"  FAIL {name}" + (f" — {detail}" if detail else ""))


def quiet(fn, *args, **kwargs):
    """출력을 삼키고 반환값을 준다 — 테스트 로그를 어지럽히지 않는다."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = fn(*args, **kwargs)
    return result, buf.getvalue()


GRAPH = {
    "id": "t-graph", "version": "1.0.0", "description": "테스트 그래프",
    "requires": "L1", "degrade_to": "L1",
    "nodes": [
        {"id": "author", "skill": "inline", "role": "prd.author", "runtime": None,
         "tier": None, "requires": "L1", "inputs": [], "output_contract": None,
         "gate": None, "retry": {"max": 1, "on": ["error"]}, "on_failure": "halt",
         "timeout_sec": 60, "prompt": "PRD 를 쓴다."},
        {"id": "review", "skill": "inline", "role": "prd.review", "runtime": None,
         "tier": None, "requires": "L0", "inputs": ["author"],
         "output_contract": "contracts/review-verdict.schema.json", "gate": None,
         "retry": {"max": 2, "on": ["verdict_request_changes", "contract_violation"],
                   "to": "author"},
         "on_failure": "halt", "timeout_sec": 60, "prompt": "PRD 를 검수한다."},
        {"id": "approve", "skill": "inline", "role": "design.review", "runtime": None,
         "tier": None, "requires": "L0", "inputs": ["review"], "output_contract": None,
         "gate": "user-approval", "retry": {"max": 0, "on": []}, "on_failure": "halt",
         "timeout_sec": 60, "prompt": "승인 체크리스트."},
    ],
}
GRAPH_PATH = os.path.join(TMP, "t-graph.json")
json.dump(GRAPH, open(GRAPH_PATH, "w"), ensure_ascii=False)

roles = h.load("roles.json")


def fresh_state():
    """run new 를 직접 부르지 않고 state 를 만든다 (경로 의존 최소화)."""
    state = {"run_id": "t-run", "graph": GRAPH_PATH, "profile": "cross-review",
             "level": "L2", "objective": "테스트", "created_at": h.now_iso(), "nodes": {}}
    for n in GRAPH["nodes"]:
        state["nodes"][n["id"]] = {"status": "pending", "attempts": 0,
                                   "gate": n.get("gate"), "degraded": None}
    d = h.run_dir("t-run")
    if os.path.isdir(d):
        shutil.rmtree(d)
    h.save_state(state)
    return state


VERDICT_OK = {"verdict": "APPROVED", "findings": [],
              "reviewed": {"files_changed": 3, "files_read": 3},
              "summary_md": "문제 없음"}

print("── 회귀: ready 셋 ──")

state = fresh_state()
graph_nodes = {n["id"]: n for n in GRAPH["nodes"]}
check("시작 노드만 ready", h.ready_nodes(state, graph_nodes) == ["author"],
      str(h.ready_nodes(state, graph_nodes)))
state["nodes"]["author"]["status"] = "completed"
check("선행 완료 후 후행 ready", h.ready_nodes(state, graph_nodes) == ["review"],
      str(h.ready_nodes(state, graph_nodes)))

print("── 회귀: done · 계약 위반 ──")

state = fresh_state()
state["nodes"]["author"]["status"] = "completed"
rc, _ = quiet(h.apply_done, state, GRAPH, roles, "review", {"verdict": "APPROVED"})
check("계약 위반은 completed 가 아니다",
      state["nodes"]["review"]["status"] != "completed",
      state["nodes"]["review"]["status"])
check("계약 위반은 exit 1", rc == 1, str(rc))
check("시도 카운트 증가", state["nodes"]["review"]["attempts"] == 1,
      str(state["nodes"]["review"]["attempts"]))
check("사유 기록", "contract_violation" in (state["nodes"]["review"].get("reason") or ""),
      str(state["nodes"]["review"].get("reason")))

print("── 회귀: done · 정상 ──")

state = fresh_state()
state["nodes"]["author"]["status"] = "completed"
rc, _ = quiet(h.apply_done, state, GRAPH, roles, "review", VERDICT_OK)
check("계약 통과 시 completed", state["nodes"]["review"]["status"] == "completed",
      state["nodes"]["review"]["status"])
check("정상은 exit 0", rc == 0, str(rc))
saved = os.path.join(h.run_dir("t-run"), "review", "result.json")
check("산출물 기록", os.path.isfile(saved), saved)

print("── 회귀: 게이트 ──")

state = fresh_state()
state["nodes"]["author"]["status"] = "completed"
state["nodes"]["review"]["status"] = "completed"
quiet(h.apply_done, state, GRAPH, roles, "approve", None)
check("gate 선언 노드는 awaiting-gate",
      state["nodes"]["approve"]["status"] == "awaiting-gate",
      state["nodes"]["approve"]["status"])

print("── 회귀: REQUEST_CHANGES 루프백 ──")

state = fresh_state()
state["nodes"]["author"]["status"] = "completed"
rc_data = dict(VERDICT_OK, verdict="REQUEST_CHANGES",
               findings=[{"level": "p1", "file": "a.kt", "line": 1,
                          "problem": "레이어 의존 방향이 뒤집혔습니다",
                          "direction": "Repository 인터페이스를 domain 으로 옮기세요"}])
quiet(h.apply_done, state, GRAPH, roles, "review", rc_data)
check("retry.to 노드 재개방", state["nodes"]["author"]["status"] == "pending",
      state["nodes"]["author"]["status"])
check("리뷰는 완료로 기록하지 않음", state["nodes"]["review"]["status"] != "completed",
      state["nodes"]["review"]["status"])

print("── 회귀: fail 정책 ──")

state = fresh_state()
quiet(h.apply_fail, state, GRAPH, roles, "author", "CLI 없음", "error")
check("retry.on 에 있으면 재시도", state["nodes"]["author"]["status"] == "pending",
      state["nodes"]["author"]["status"])
quiet(h.apply_fail, state, GRAPH, roles, "author", "또 실패", "error")
check("재시도 소진 시 failed", state["nodes"]["author"]["status"] == "failed",
      state["nodes"]["author"]["status"])

state = fresh_state()
quiet(h.apply_fail, state, GRAPH, roles, "author", "계약 깨짐", "contract_violation")
check("retry.on 에 없는 kind 는 즉시 failed",
      state["nodes"]["author"]["status"] == "failed", state["nodes"]["author"]["status"])

# ─────────────────────────────────────────────────────────── 디스패처 통합

print("── 노드 스펙 조립 ──")

state = fresh_state()
spec = h.build_node_spec(state, GRAPH, roles, "author")
check("페르소나 파일 경로", spec["agent_file"].endswith("agents/private-prd-writer.md")
      and os.path.isfile(spec["agent_file"]), str(spec.get("agent_file")))
check("런타임 해석", spec["runtime"] == "codex", str(spec.get("runtime")))
check("모델 해석", spec["model"] == "gpt-5.6-terra", str(spec.get("model")))
check("접근 등급 투영 (codex → sandbox)", spec.get("sandbox") == "workspace-write", str(spec))
check("codex 는 tools 미지원 → 제거", "tools" not in spec, str(spec))
check("제거 사실 기록", any("tools" in n for n in spec.get("_dropped", [])),
      str(spec.get("_dropped")))
check("타임아웃 승계", spec["timeout_sec"] == 60, str(spec.get("timeout_sec")))
check("프롬프트 승계", "PRD" in spec["prompt"], str(spec.get("prompt")))
check("업스트림 없음", spec["upstream"] == [], str(spec["upstream"]))

state["nodes"]["author"]["status"] = "completed"
outdir = os.path.join(h.run_dir("t-run"), "author")
os.makedirs(outdir, exist_ok=True)
open(os.path.join(outdir, "result.json"), "w").write("{}")
spec2 = h.build_node_spec(state, GRAPH, roles, "review")
check("업스트림 경로 주입", len(spec2["upstream"]) == 1
      and spec2["upstream"][0][0] == "author", str(spec2["upstream"]))
check("계약 파일 경로", (spec2.get("contract_file") or "").endswith("review-verdict.schema.json"),
      str(spec2.get("contract_file")))
check("claude 는 tools 유지", spec2.get("tools") and "Read" in spec2["tools"], str(spec2))
check("claude 접근 등급 → permission_mode", spec2.get("permission_mode") == "dontAsk",
      str(spec2))

print("── objective 자동 주입 ──")

# 노드 프롬프트의 {{objective}} 를 run 의 objective 로 자동 채운다. 채우지 않으면
# 실행 전 검증이 "미치환 자리표시자" 로 막는다 (조용히 넘어가지 않는다).
OBJ_GRAPH = json.loads(json.dumps(GRAPH))
OBJ_GRAPH["nodes"][0]["prompt"] = "요구사항: {{objective}} 를 PRD 로 쓴다."
OBJ_PATH = os.path.join(TMP, "t-obj.json")
json.dump(OBJ_GRAPH, open(OBJ_PATH, "w"), ensure_ascii=False)

state = fresh_state()
state["graph"] = OBJ_PATH
state["objective"] = "대여 반납 기능"
rc, out = quiet(h.dispatch_ready, state, OBJ_GRAPH, roles, dry_run=True)
check("objective 자동 주입으로 검증 통과", rc == 0, f"{rc} / {out[:200]}")

state = fresh_state()
state["graph"] = OBJ_PATH
state["objective"] = ""
h.errors.clear()
rc, out = quiet(h.dispatch_ready, state, OBJ_GRAPH, roles, dry_run=True)
check("빈 objective 도 치환은 성공", rc == 0, f"{rc} / {out[:200]}")

MISS_GRAPH = json.loads(json.dumps(GRAPH))
MISS_GRAPH["nodes"][0]["prompt"] = "티켓 {{ticket}} 을 구현한다."
state = fresh_state()
h.errors.clear()
rc, out = quiet(h.dispatch_ready, state, MISS_GRAPH, roles, dry_run=True)
check("미치환 자리표시자는 0개 노드 실행", rc == 1, f"{rc} / {out[:200]}")
check("어느 자리표시자인지 보고", any("ticket" in e for e in h.errors), str(h.errors))
# 드라이런이 통과한 그래프가 실행에서 죽으면 드라이런의 의미가 없다 — 계획 출력보다 검증이 앞선다.
check("검증 실패 시 계획을 출력하지 않는다", "디스패치" not in out, out[:200])
h.errors.clear()

print("── 실제 그래프 노드에 prompt 존재 ──")

real_graph = h.load("orchestration/private-feature.json")
noprompt = [n["id"] for n in real_graph["nodes"] if not (n.get("prompt") or "").strip()]
check("private-feature 전 노드에 prompt", noprompt == [], str(noprompt))
check("prd 노드는 objective 를 참조", "{{objective}}" in real_graph["nodes"][0]["prompt"],
      real_graph["nodes"][0]["prompt"][:60])

print("── dispatch --dry-run ──")

state = fresh_state()
rc, out = quiet(h.dispatch_ready, state, GRAPH, roles, dry_run=True, max_parallel=4)
check("dry-run 은 exit 0", rc == 0, str(rc))
check("dry-run 은 상태를 바꾸지 않는다", state["nodes"]["author"]["status"] == "pending",
      state["nodes"]["author"]["status"])
check("계획에 노드·런타임 표기", "author" in out and "codex" in out, out[:200])

print("── dispatch 실행 (가짜 CLI) ──")

binp = os.path.join(TMP, "bin")
os.makedirs(binp, exist_ok=True)
fake = os.path.join(binp, "codex")
with open(fake, "w") as f:
    f.write('''#!/bin/sh
out=""
while [ $# -gt 0 ]; do
  if [ "$1" = "-o" ]; then out="$2"; fi
  shift
done
echo '{"doc_path": "x.md", "ok": true}' > "$out"
''')
os.chmod(fake, os.stat(fake).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
os.environ["PATH"] = binp + os.pathsep + os.environ["PATH"]

state = fresh_state()
rc, out = quiet(h.dispatch_ready, state, GRAPH, roles, max_parallel=2)
check("계약 없는 노드는 실행 후 completed",
      state["nodes"]["author"]["status"] == "completed",
      state["nodes"]["author"]["status"])
check("dispatch exit 0", rc == 0, f"{rc} / {out[:300]}")
check("산출물이 state 경로에 기록",
      os.path.isfile(os.path.join(h.run_dir("t-run"), "author", "result.json")))

print("── host 런타임 제외 ──")

state = fresh_state()
state["profile"] = "portable"   # 전 role 이 host 로 떨어진다
rc, out = quiet(h.dispatch_ready, state, GRAPH, roles, dry_run=True)
check("host 노드는 디스패처 대상 아님", "host" in out and "수동" in out, out[:300])
check("host 만 있으면 실행할 것이 없다", state["nodes"]["author"]["status"] == "pending",
      state["nodes"]["author"]["status"])

print("── 티켓 자식 프롬프트에 배정 정보 ──")

# 티켓이 명시되지 않으면 18개 자식이 전부 같은 프롬프트를 받는다 — 자기가 무슨 티켓인지 모른다.
FANP = json.loads(json.dumps(GRAPH))
FANP["nodes"] = [
    {"id": "plan", "skill": "inline", "role": "plan.coordinate", "runtime": None,
     "tier": None, "requires": "L2", "inputs": [], "output_contract": None,
     "gate": None, "retry": {"max": 0, "on": []}, "on_failure": "halt",
     "timeout_sec": 60, "prompt": "통합 DAG"},
    {"id": "implement", "skill": "inline", "role": "implement.be", "runtime": None,
     "tier": None, "requires": "L1", "inputs": ["plan"],
     "fanout": {"from": "plan", "key": "tickets", "role_from": "role",
                "roles": ["implement.be", "implement.mysql"]},
     "output_contract": None, "gate": None,
     "retry": {"max": 0, "on": []}, "on_failure": "halt", "timeout_sec": 60,
     "prompt": "배정된 티켓을 TDD 순서로 구현한다."},
]
FANP_PATH = os.path.join(TMP, "t-fanp.json")
json.dump(FANP, open(FANP_PATH, "w"), ensure_ascii=False)

TICKETS = [
    {"id": "BE-01", "role": "implement.be", "title": "도메인 계약 정의",
     "depends_on": [], "files_touched": ["autotrading/domain/"],
     "path": "/tmp/tickets/BE-01-계약.md", "size": "M"},
    {"id": "BE-02", "role": "implement.be", "title": "애그리게이트",
     "depends_on": ["BE-01"], "files_touched": ["autotrading/domain/A.kt"]},
]

st = {"run_id": "t-fanp", "graph": FANP_PATH, "profile": "cross-review", "level": "L2",
      "objective": "테스트", "created_at": h.now_iso(), "nodes": {}}
for n in FANP["nodes"]:
    st["nodes"][n["id"]] = {"status": "pending", "attempts": 0, "gate": None,
                            "degraded": None}
st["nodes"]["plan"]["status"] = "completed"
rd = h.run_dir("t-fanp")
if os.path.isdir(rd):
    shutil.rmtree(rd)
os.makedirs(os.path.join(rd, "plan"), exist_ok=True)
json.dump({"tickets": TICKETS}, open(os.path.join(rd, "plan", "result.json"), "w"),
          ensure_ascii=False)
h.save_state(st)
h.expand_fanout(st, {n["id"]: n for n in FANP["nodes"]})

spec = h.build_node_spec(st, FANP, roles, "implement[BE-01]")
check("스펙에 티켓 데이터", (spec.get("ticket") or {}).get("id") == "BE-01",
      str(spec.get("ticket")))

disp = h.load_runner("dispatch")
text = disp.build_prompt(spec, {})
check("프롬프트에 티켓 ID", "BE-01" in text, text[:200])
check("프롬프트에 티켓 제목", "도메인 계약 정의" in text, "제목 없음")
# "티켓이 소유하지 않은 파일은 수정하지 않는다" 를 지키려면 소유 범위를 알아야 한다.
check("프롬프트에 소유 경로", "autotrading/domain/" in text, "소유 경로 없음")
check("프롬프트에 티켓 md 경로", "BE-01-계약.md" in text, "md 경로 없음")

# BE-02 는 BE-01 을 의존하므로 그 산출물이 있어야 프롬프트가 조립된다 (실행 전 검증).
os.makedirs(os.path.join(rd, "implement[BE-01]"), exist_ok=True)
open(os.path.join(rd, "implement[BE-01]", "result.json"), "w").write('{"status":"done"}')

spec2 = h.build_node_spec(st, FANP, roles, "implement[BE-02]")
text2 = disp.build_prompt(spec2, {})
check("티켓마다 프롬프트가 다르다", text != text2)
check("BE-02 는 자기 정보만", "BE-02" in text2 and "애그리게이트" in text2, text2[:200])
check("선행 티켓을 알려준다", "BE-01" in text2, "의존 표기 없음")
# path 가 없는 티켓도 깨지지 않아야 한다 (선택 필드).
check("md 경로 없는 티켓도 조립됨", "BE-02" in text2)

# fanout 자식이 아닌 노드는 배정 섹션이 없다.
plan_spec = h.build_node_spec(st, FANP, roles, "plan")
check("일반 노드엔 티켓 데이터 없음", plan_spec.get("ticket") is None,
      str(plan_spec.get("ticket")))
check("일반 노드 프롬프트에 배정 섹션 없음",
      "# 배정" not in disp.build_prompt(plan_spec, {}))

print("── run wave: 티켓 워크트리 배치 ──")

FAN_GRAPH = {
    "id": "t-fan", "version": "1.0.0", "description": "fanout 테스트",
    "requires": "L2", "degrade_to": "L1",
    "nodes": [
        {"id": "plan", "skill": "inline", "role": "plan.coordinate", "runtime": None,
         "tier": None, "requires": "L2", "inputs": [],
         "output_contract": None, "gate": None,
         "retry": {"max": 0, "on": []}, "on_failure": "halt", "timeout_sec": 60,
         "prompt": "통합 DAG 를 만든다."},
        {"id": "implement", "skill": "inline", "role": "implement.be", "runtime": None,
         "tier": None, "requires": "L1", "inputs": ["plan"],
         "fanout": {"from": "plan", "key": "tickets", "role_from": "role",
                    "roles": ["implement.be", "implement.fe", "implement.mysql"]},
         "output_contract": None, "gate": None,
         "retry": {"max": 0, "on": []}, "on_failure": "halt", "timeout_sec": 60,
         "prompt": "티켓을 구현한다."},
    ],
}
FAN_PATH = os.path.join(TMP, "t-fan.json")
json.dump(FAN_GRAPH, open(FAN_PATH, "w"), ensure_ascii=False)


def make_repo(name):
    repo = os.path.join(TMP, name)
    os.makedirs(repo, exist_ok=True)
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    import subprocess as sp
    sp.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True, env=env)
    open(os.path.join(repo, "README.md"), "w").write("x")
    sp.run(["git", "add", "."], cwd=repo, check=True, env=env)
    sp.run(["git", "commit", "-qm", "init"], cwd=repo, check=True, env=env)
    return repo


def fan_state(tickets, run_id="t-fan-run"):
    state = {"run_id": run_id, "graph": FAN_PATH, "profile": "cross-review",
             "level": "L2", "objective": "테스트", "created_at": h.now_iso(), "nodes": {}}
    for n in FAN_GRAPH["nodes"]:
        state["nodes"][n["id"]] = {"status": "pending", "attempts": 0,
                                   "gate": None, "degraded": None}
    d = h.run_dir(run_id)
    if os.path.isdir(d):
        shutil.rmtree(d)
    state["nodes"]["plan"]["status"] = "completed"
    out = os.path.join(d, "plan")
    os.makedirs(out, exist_ok=True)
    json.dump({"tickets": tickets}, open(os.path.join(out, "result.json"), "w"),
              ensure_ascii=False)
    h.save_state(state)
    return state


def TK(tid, role, depends=(), owns=()):
    return {"id": tid, "role": role, "title": tid, "depends_on": list(depends),
            "files_touched": list(owns)}


repo = make_repo("target-repo")
tickets = [TK("BE-01", "implement.be", owns=["src/domain/rental/"]),
           TK("DB-01", "implement.mysql", owns=["src/main/resources/db/"]),
           TK("BE-02", "implement.be", depends=["BE-01"], owns=["src/app/rental/"]),
           TK("FE-01", "implement.fe", depends=["BE-02"], owns=["web/src/rental/"])]

state = fan_state(tickets)
rc, out = quiet(h.dispatch_wave, state, FAN_GRAPH, roles, repo=repo, plan_only=True)
check("plan-only 는 exit 0", rc == 0, f"{rc} / {out[:200]}")
check("티켓 wave 3개", "티켓 wave 3개" in out, out[:400])
check("wave1 너비 2", "wave 1 (너비 2)" in out, out[:400])
check("워크트리 루트 규약", "target-repo-worktrees" in out, out[:400])
check("plan-only 는 워크트리를 만들지 않는다",
      not os.path.isdir(os.path.join(TMP, "target-repo-worktrees")))

# 같은 wave 의 소유 경로가 겹치면 병렬 실행이 곧 머지 충돌이다.
clash = [TK("BE-01", "implement.be", owns=["src/domain/rental/"]),
         TK("BE-09", "implement.be", owns=["src/domain/rental/"])]
state = fan_state(clash, "t-fan-clash")
rc, out = quiet(h.dispatch_wave, state, FAN_GRAPH, roles, repo=repo, plan_only=True)
check("소유 교집합은 실행 차단", rc == 1, f"{rc} / {out[:300]}")
check("충돌 내용 보고", "rental" in out, out[:400])

h.errors.clear()
rc, out = quiet(h.dispatch_wave, state, FAN_GRAPH, roles, repo=repo,
                plan_only=True, allow_overlap=True)
check("--allow-overlap 은 통과", rc == 0, f"{rc} / {out[:300]}")

# 모든 wave 너비가 1~2 면 직선형 — 분해 실패다.
h.warns.clear()
linear = [TK("BE-01", "implement.be", owns=["a/"]),
          TK("BE-02", "implement.be", depends=["BE-01"], owns=["b/"]),
          TK("BE-03", "implement.be", depends=["BE-02"], owns=["c/"])]
state = fan_state(linear, "t-fan-linear")
quiet(h.dispatch_wave, state, FAN_GRAPH, roles, repo=repo, plan_only=True)
check("직선형 DAG 경고", any("직선형" in w for w in h.warns), str(h.warns))

# 실제 워크트리 배치 — dry-run 이 아니면 트리를 만들고 노드 cwd 에 심는다.
h.errors.clear(); h.warns.clear()
state = fan_state(tickets, "t-fan-exec")
rc, out = quiet(h.dispatch_wave, state, FAN_GRAPH, roles, repo=repo, dry_run=True)
ready_children = [n for n, v in state["nodes"].items() if v.get("cwd")]
check("ready 자식에만 cwd 배치", sorted(ready_children)
      == ["implement[BE-01]", "implement[DB-01]"], str(sorted(ready_children)))
check("cwd 가 티켓별 워크트리",
      state["nodes"]["implement[BE-01]"]["cwd"].endswith("be-01"),
      state["nodes"]["implement[BE-01]"]["cwd"])
check("후행 티켓은 아직 미배치",
      state["nodes"]["implement[BE-02]"].get("cwd") is None)

state = fan_state(tickets, "t-fan-real")
rc, out = quiet(h.dispatch_wave, state, FAN_GRAPH, roles, repo=repo, plan_only=False,
                dry_run=False, max_parallel=2, base="main")
wt = state["nodes"]["implement[BE-01]"]["cwd"]
check("실제 워크트리 생성", os.path.isdir(wt) and os.path.isfile(
    os.path.join(wt, "README.md")), wt)
check("노드 스펙이 워크트리 cwd 를 쓴다",
      h.build_node_spec(state, FAN_GRAPH, roles, "implement[BE-01]")["cwd"] == wt, wt)

# 기준 ref 가 없으면 조용히 다른 커밋 위에 얹지 않고 멈춘다.
h.errors.clear()
fresh_repo = make_repo("nobase-repo")   # 앞 케이스가 만든 브랜치·트리와 격리한다
state = fan_state(tickets, "t-fan-nobase")
rc, out = quiet(h.dispatch_wave, state, FAN_GRAPH, roles, repo=fresh_repo,
                plan_only=False, dry_run=False, base="origin/nope")
check("기준 ref 부재 시 중단", rc == 1, f"{rc} / {out[:200]}")
check("해결 방법 안내", any("fetch" in e or "--base" in e for e in h.errors), str(h.errors))

# 레포가 아니면 실행 전에 멈춘다.
h.errors.clear()
state = fan_state(tickets, "t-fan-norepo")
rc, out = quiet(h.dispatch_wave, state, FAN_GRAPH, roles,
                repo=os.path.join(TMP, "not-a-repo"), plan_only=True)
check("git 저장소가 아니면 중단", rc == 1, f"{rc} / {out[:200]}")

# fanout 이 전개되지 않았으면 (선행 미완료) 중단한다.
h.errors.clear()
state = fan_state(tickets, "t-fan-pending")
state["nodes"]["plan"]["status"] = "pending"
state["nodes"].pop("implement[BE-01]", None)
state["nodes"]["implement"].pop("children", None)
rc, out = quiet(h.dispatch_wave, state, FAN_GRAPH, roles, repo=repo, plan_only=True)
check("fanout 미전개 시 중단", rc == 1, f"{rc} / {out[:200]}")

h.errors.clear(); h.warns.clear()

shutil.rmtree(TMP, ignore_errors=True)
print()
if failures:
    print(f"실패 {len(failures)}건: {failures}")
    sys.exit(1)
print("전부 통과")
