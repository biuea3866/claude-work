#!/usr/bin/env python3
"""티켓 md → plan 산출물 브릿지 테스트.

손으로 쓴 티켓 md 를 contracts/design-doc.schema.json 을 만족하는 plan 결과로 바꾼다.
파이프라인이 생성하지 않은 티켓으로도 `harness run wave` 를 돌리기 위한 계층이다.

실행: python3 tests/test_plan_from_tickets.py
"""
import importlib.machinery
import importlib.util
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
b = load_module("orchestration/runner/tickets.py", "harness_tickets")

failures = []
TMP = tempfile.mkdtemp(prefix="harness-tickets-")


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        failures.append(name)
        print(f"  FAIL {name}" + (f" — {detail}" if detail else ""))


def expect_fail(name, fn, needle=""):
    try:
        fn()
    except b.TicketError as e:
        check(name, needle in str(e), f"메시지에 '{needle}' 없음: {e}")
        return
    except Exception as e:  # noqa: BLE001
        check(name, False, f"TicketError 가 아닌 예외: {type(e).__name__}: {e}")
        return
    check(name, False, "예외가 나지 않았다")


def write_ticket(d, name, title, deps, body=""):
    path = os.path.join(d, name)
    dep_line = ", ".join(deps) if deps else "없음"
    open(path, "w").write(
        f"---\ntitle: \"{title}\"\n---\n\n# {title}\n\n"
        f"## 작업 내용 (설계 의도)\n\n### 변경 사항\n{body}\n\n"
        f"## 의존\n- {dep_line}\n\n## 테스트 케이스\n- 케이스\n")
    return path


def write_dag(d, rows):
    """최소 소유 경로 표. 소유 경로가 없으면 파서가 (정당하게) 거부한다."""
    lines = ["| 티켓 | 수정 파일 범위 |", "|---|---|"]
    lines += [f"| {tid} | `{path}` |" for tid, path in rows]
    open(os.path.join(d, "_분해-DAG.md"), "w").write("\n".join(lines) + "\n")


DAG = """# 분해 DAG

## Single Writer per File

### Wave 1

| 티켓 | 수정 파일 범위 |
|---|---|
| DB-01 | `backend/db/migration/V1__x.sql` |
| BE-01 | `autotrading/domain/` |

### Wave 2

| 티켓 | 수정 파일 범위 |
|---|---|
| BE-02 | `autotrading/domain/A.kt`, `autotrading/infrastructure/A*` |
| BE-03 | `autotrading/domain/B.kt`·`C.kt` |
"""

print("── 파싱 ──")

d = os.path.join(TMP, "tickets")
os.makedirs(d)
write_ticket(d, "DB-01-스키마.md", "[DB-01] 테이블 생성", [], "Flyway 로 5개 테이블을 만든다.")
write_ticket(d, "BE-01-계약.md", "[BE-01] 도메인 계약", [], "enum·값객체·interface 를 확정한다.")
write_ticket(d, "BE-02-애그리게이트.md", "[BE-02] A 애그리게이트", ["BE-01", "DB-01"])
write_ticket(d, "BE-03-애그리게이트.md", "[BE-03] B 애그리게이트", ["BE-01", "DB-01"])
open(os.path.join(d, "_분해-DAG.md"), "w").write(DAG)

plan = b.plan_from_tickets(d)
ids = [t["id"] for t in plan["tickets"]]
check("티켓 전량 수집 (_ 접두 파일 제외)", ids == ["BE-01", "BE-02", "BE-03", "DB-01"], str(ids))

by_id = {t["id"]: t for t in plan["tickets"]}
check("의존 파싱", by_id["BE-02"]["depends_on"] == ["BE-01", "DB-01"],
      str(by_id["BE-02"]["depends_on"]))
check("의존 없음 → 빈 배열", by_id["BE-01"]["depends_on"] == [],
      str(by_id["BE-01"]["depends_on"]))
check("제목 파싱", by_id["BE-01"]["title"] == "도메인 계약", by_id["BE-01"]["title"])

print("── role 판정 (접두사 추론 금지) ──")

check("BE → implement.be", by_id["BE-01"]["role"] == "implement.be", by_id["BE-01"]["role"])
# DB 는 mysql/mongodb 로 갈려 접두사만으로 결정할 수 없다 — 본문 근거로 판정한다.
check("DB + Flyway → implement.mysql", by_id["DB-01"]["role"] == "implement.mysql",
      by_id["DB-01"]["role"])

d2 = os.path.join(TMP, "t2")
os.makedirs(d2)
write_ticket(d2, "DB-01-컬렉션.md", "[DB-01] 컬렉션 생성",
             [], "MongoDB 컬렉션과 JSON Schema validator 를 만든다.")
write_dag(d2, [("DB-01", "mongo/migration/")])
check("DB + Mongo → implement.mongodb",
      b.plan_from_tickets(d2)["tickets"][0]["role"] == "implement.mongodb")

d3 = os.path.join(TMP, "t3")
os.makedirs(d3)
write_ticket(d3, "DB-01-무근거.md", "[DB-01] 저장소 작업", [], "테이블을 만든다.")
write_dag(d3, [("DB-01", "db/x")])
expect_fail("DB 근거 없으면 추측하지 않고 실패",
            lambda: b.plan_from_tickets(d3), "판정할 수 없습니다")

d4 = os.path.join(TMP, "t4")
os.makedirs(d4)
write_ticket(d4, "INFRA-01-토픽.md", "[INFRA-01] 토픽 생성", [], "Kafka 토픽 파티션을 정의한다.")
write_dag(d4, [("INFRA-01", "kafka/topics/")])
check("INFRA + Kafka → implement.kafka",
      b.plan_from_tickets(d4)["tickets"][0]["role"] == "implement.kafka")

d5 = os.path.join(TMP, "t5")
os.makedirs(d5)
write_ticket(d5, "INFRA-01-캐시.md", "[INFRA-01] 캐시 키", [], "Redis 키 스키마와 TTL 을 정한다.")
write_dag(d5, [("INFRA-01", "redis/keys/")])
check("INFRA + Redis → implement.redis",
      b.plan_from_tickets(d5)["tickets"][0]["role"] == "implement.redis")

print("── 소유 경로 (Single Writer 입력) ──")

check("DAG 표에서 소유 경로 수집",
      by_id["BE-02"]["files_touched"] == ["autotrading/domain/A.kt",
                                          "autotrading/infrastructure/A*"],
      str(by_id["BE-02"]["files_touched"]))
# 가운뎃점(·)도 구분자로 쓰인다 — 실제 티켓이 그렇게 쓴다.
check("가운뎃점 구분자 처리",
      by_id["BE-03"]["files_touched"] == ["autotrading/domain/B.kt", "C.kt"],
      str(by_id["BE-03"]["files_touched"]))

d6 = os.path.join(TMP, "t6")
os.makedirs(d6)
write_ticket(d6, "BE-01-x.md", "[BE-01] x", [])
# 소유 경로가 없으면 Single Writer 검증을 할 수 없다 — 조용히 통과시키지 않는다.
expect_fail("DAG 없으면 실패", lambda: b.plan_from_tickets(d6), "소유 경로")

print("── wave·계약 ──")

check("wave 분포 계산", [len(w["ticket_ids"]) for w in plan["waves"]] == [2, 2],
      str(plan["waves"]))
check("max_wave_width", plan["max_wave_width"] == 2, str(plan.get("max_wave_width")))
# 모든 wave 너비가 1~2 면 직선형 — 계약의 의미 규칙이 거부해야 한다.
problems = h.validate_result("contracts/design-doc.schema.json", plan)
check("직선형은 계약이 거부한다", any("직선형" in p for p in problems), str(problems))
check("요약에 직선형 경고", "직선형" in plan["summary_md"], plan["summary_md"])

# 너비 3 이상이 하나라도 있으면 통과한다.
dw = os.path.join(TMP, "tw")
os.makedirs(dw)
write_ticket(dw, "BE-01-a.md", "[BE-01] a", [])
for i in (2, 3, 4):
    write_ticket(dw, f"BE-0{i}-x.md", f"[BE-0{i}] x", ["BE-01"])
write_dag(dw, [("BE-01", "a/"), ("BE-02", "b/"), ("BE-03", "c/"), ("BE-04", "d/")])
plan_wide = b.plan_from_tickets(dw)
check("비직선형 계약 통과",
      h.validate_result("contracts/design-doc.schema.json", plan_wide) == [],
      str(h.validate_result("contracts/design-doc.schema.json", plan_wide)))

print("── 순환·미해결 의존 ──")

d7 = os.path.join(TMP, "t7")
os.makedirs(d7)
write_ticket(d7, "BE-01-a.md", "[BE-01] a", ["BE-02"])
write_ticket(d7, "BE-02-b.md", "[BE-02] b", ["BE-01"])
open(os.path.join(d7, "_분해-DAG.md"), "w").write(
    "| 티켓 | 수정 파일 범위 |\n|---|---|\n| BE-01 | `a/` |\n| BE-02 | `b/` |\n")
expect_fail("순환 의존은 실패", lambda: b.plan_from_tickets(d7), "순환")

d8 = os.path.join(TMP, "t8")
os.makedirs(d8)
write_ticket(d8, "BE-01-a.md", "[BE-01] a", ["BE-99"])
open(os.path.join(d8, "_분해-DAG.md"), "w").write(
    "| 티켓 | 수정 파일 범위 |\n|---|---|\n| BE-01 | `a/` |\n")
expect_fail("없는 티켓 의존은 실패", lambda: b.plan_from_tickets(d8), "BE-99")

print("── 같은 wave 소유 교집합 ──")

d9 = os.path.join(TMP, "t9")
os.makedirs(d9)
write_ticket(d9, "BE-01-a.md", "[BE-01] a", [])
write_ticket(d9, "BE-02-b.md", "[BE-02] b", [])
open(os.path.join(d9, "_분해-DAG.md"), "w").write(
    "| 티켓 | 수정 파일 범위 |\n|---|---|\n| BE-01 | `same/` |\n| BE-02 | `same/` |\n")
# 계약의 의미 규칙이 잡아야 한다 (Single Writer per File).
plan9 = b.plan_from_tickets(d9)
problems9 = h.validate_result("contracts/design-doc.schema.json", plan9)
check("같은 wave 교집합은 계약 검증에서 걸린다", problems9 != [], str(problems9))

print("── 실제 자동매매봇 티켓 ──")

REAL = os.path.expanduser(
    "~/Desktop/dpdpdndn/프로젝트/주식앱/자동매매봇/Tickets")
if os.path.isdir(REAL):
    real = b.plan_from_tickets(REAL)
    check("티켓 19개 중 18개 수집 (_분해-DAG 제외)", len(real["tickets"]) == 18,
          str(len(real["tickets"])))
    widths = [len(w["ticket_ids"]) for w in real["waves"]]
    # 티켓 md 의 `## 의존` 이 정본이다 (rules/private-ticket.md). 분해 DAG 문서의 선언값이
    # 아니라 실제 의존에서 계산한다 — 문서가 BE-11 을 자기 의존(BE-10)과 같은 wave 에 둔
    # 오류가 이 검사로 드러났다.
    check("선행 wave 2개는 문서와 일치", widths[:2] == [2, 8], str(widths))
    wave_of = {tid: w["index"] for w in real["waves"] for tid in w["ticket_ids"]}
    real_by2 = {t["id"]: t for t in real["tickets"]}
    # 어느 티켓도 자기 의존과 같은(또는 앞선) wave 에 있을 수 없다.
    violations = [(tid, dep) for tid, spec in real_by2.items()
                  for dep in spec["depends_on"] if wave_of[dep] >= wave_of[tid]]
    check("의존이 항상 앞 wave 에 온다", violations == [], str(violations))
    check("BE-11 은 BE-10 보다 뒤 wave", wave_of["BE-11"] > wave_of["BE-10"],
          f"BE-10 w{wave_of['BE-10']} / BE-11 w{wave_of['BE-11']}")
    real_by = {t["id"]: t for t in real["tickets"]}
    check("DB-01 → implement.mysql", real_by["DB-01"]["role"] == "implement.mysql",
          real_by["DB-01"]["role"])
    check("BE 전량 → implement.be",
          all(t["role"] == "implement.be" for t in real["tickets"] if t["id"].startswith("BE")))
    check("전 티켓에 소유 경로",
          all(t["files_touched"] for t in real["tickets"]),
          str([t["id"] for t in real["tickets"] if not t["files_touched"]]))
    problems = h.validate_result("contracts/design-doc.schema.json", real)
    check("실제 티켓이 계약 통과", problems == [], str(problems))
else:
    print(f"  skip 실제 티켓 디렉토리 없음 — {REAL}")

print("── CLI: harness plan from-tickets ──")

import io, contextlib, subprocess

HB = os.path.join(ROOT, "bin", "harness")
out_path = os.path.join(TMP, "plan.json")
proc = subprocess.run([sys.executable, HB, "plan", "from-tickets", dw,
                       "--out", out_path], capture_output=True, text=True, cwd=ROOT)
check("plan from-tickets exit 0", proc.returncode == 0, proc.stdout + proc.stderr)
check("파일로 저장", os.path.isfile(out_path))
saved = json.load(open(out_path))
check("저장 내용이 계약 통과",
      h.validate_result("contracts/design-doc.schema.json", saved) == [],
      str(h.validate_result("contracts/design-doc.schema.json", saved)))
check("role 배정 출력", "implement.be" in proc.stdout, proc.stdout[:200])
check("wave 요약 출력", "wave" in proc.stdout, proc.stdout[:200])

proc = subprocess.run([sys.executable, HB, "plan", "from-tickets",
                       os.path.join(TMP, "nope")], capture_output=True, text=True, cwd=ROOT)
check("없는 디렉토리는 exit 1", proc.returncode == 1, str(proc.returncode))

# 직선형 DAG 는 계약 위반이므로 exit 1 — seed 로 못 넘어간다.
proc = subprocess.run([sys.executable, HB, "plan", "from-tickets", d],
                      capture_output=True, text=True, cwd=ROOT)
check("직선형 티켓은 exit 1", proc.returncode == 1, str(proc.returncode))

print("── CLI: run new --seed-plan ──")

h.RUNS = os.path.join(TMP, "runs")
os.makedirs(h.RUNS, exist_ok=True)
plan_real = b.plan_from_tickets(dw)
seed_path = os.path.join(TMP, "seed.json")
json.dump(plan_real, open(seed_path, "w"), ensure_ascii=False)

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = h.cmd_run(["new", "orchestration/private-feature.json",
                    "--objective", "씨드 테스트", "--seed-plan", seed_path])
seed_out = buf.getvalue()
check("seed-plan exit 0", rc == 0, f"{rc} / {seed_out[:300]}")

state = h.load_state()
done = [n for n, v in state["nodes"].items() if v["status"] == "completed"]
# plan 의 조상 전부 + plan 자신이 완료로 기록돼야 implement fanout 이 열린다.
check("plan 및 그 조상이 완료", set(done) >= {"prd", "prd-review", "design-be", "design-db",
                                            "design-fe", "design-review", "plan"}, str(sorted(done)))
check("implement·review 는 미완료",
      state["nodes"]["implement"]["status"] != "completed"
      and state["nodes"]["review"]["status"] != "completed",
      f"{state['nodes']['implement']['status']} / {state['nodes']['review']['status']}")
saved_plan = json.load(open(os.path.join(h.run_dir(state["run_id"]), "plan", "result.json")))
check("plan 산출물이 기록됨", len(saved_plan["tickets"]) == len(plan_real["tickets"]),
      str(len(saved_plan.get("tickets", []))))

# 조용히 건너뛰지 않는다 — 왜 완료로 기록했는지 journal 에 남아야 한다.
jl = os.path.join(h.run_dir(state["run_id"]), "journal.jsonl")
events = [json.loads(l) for l in open(jl)]
check("seed 사유가 journal 에 기록", any(e.get("event") == "seeded" for e in events),
      str([e.get("event") for e in events]))
check("사전 작성 표기", any("preauthored" in json.dumps(e, ensure_ascii=False)
                       or "사전" in json.dumps(e, ensure_ascii=False) for e in events))

# 계약 위반 plan 은 씨드하지 않는다.
bad_path = os.path.join(TMP, "bad.json")
json.dump({"tickets": []}, open(bad_path, "w"))
h.errors.clear()
with contextlib.redirect_stdout(io.StringIO()):
    rc = h.cmd_run(["new", "orchestration/private-feature.json",
                    "--objective", "x", "--seed-plan", bad_path])
check("계약 위반 plan 은 거부", rc == 1, str(rc))
# 실패한 뒤 빈 run 이 남으면 load_state() 가 그것을 집어 다음 명령이 엉뚱한 상태를 읽는다.
check("거부 시 run 을 만들지 않는다", h.load_state()["run_id"] == state["run_id"],
      h.load_state()["run_id"])
h.errors.clear()

print("── seed 후 run wave 가 티켓을 잡는다 ──")

state = h.load_state()
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = h.dispatch_wave(state, h.load(state["graph"]), h.load("roles.json"),
                         repo=ROOT, plan_only=True)
wave_out = buf.getvalue()
check("fanout 전개 후 계획 산출", rc == 0, f"{rc} / {wave_out[:300]}")
check("티켓 수 보고", f"티켓 {len(plan_real['tickets'])}개" in wave_out, wave_out[:300])
h.errors.clear()

shutil.rmtree(TMP, ignore_errors=True)
print()
if failures:
    print(f"실패 {len(failures)}건: {failures}")
    sys.exit(1)
print("전부 통과")
