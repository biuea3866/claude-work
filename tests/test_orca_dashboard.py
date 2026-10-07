#!/usr/bin/env python3
"""Orca session dashboard public-contract RED tests.

Run: python3 tests/test_orca_dashboard.py
"""
import sys

sys.dont_write_bytecode = True

import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_PATH = ROOT / "bin" / "orca-dashboard"
NOW_MS = 2_000_000
ROADMAP_STEPS = list(range(9))
PIPELINES = {"private-roadmap": ROADMAP_STEPS}


def load_dashboard():
    loader = importlib.machinery.SourceFileLoader("orca_dashboard", str(DASHBOARD_PATH))
    spec = importlib.util.spec_from_loader("orca_dashboard", loader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dashboard = load_dashboard()
failures = []


def check(name, condition, detail=""):
    if condition:
        print(f"  ok   {name}")
        return
    failures.append((name, detail))
    print(f"  FAIL {name}" + (f" — {detail}" if detail else ""))


def expect_equal(name, action, expected):
    try:
        actual = action()
    except Exception as error:  # Keep the full RED suite running after an unimplemented API.
        check(name, False, f"{type(error).__name__}: {error}")
        return
    check(name, actual == expected, f"expected={expected!r}, actual={actual!r}")


def expect_predicate(name, action, predicate, expected_description):
    try:
        actual = action()
    except Exception as error:
        check(name, False, f"{type(error).__name__}: {error}")
        return
    check(name, predicate(actual), f"expected {expected_description}, actual={actual!r}")


def status_result(**overrides):
    arguments = {
        "agent_state": "done",
        "main_state": None,
        "last_message": None,
        "tail_lines": [],
        "last_output_at": NOW_MS - 1_000,
        "now_ms": NOW_MS,
    }
    arguments.update(overrides)
    return dashboard.classify_status(**arguments)


def progress_result(**overrides):
    arguments = {
        "comment": None,
        "agent_state": "working",
        "texts": [],
        "pipelines": PIPELINES,
    }
    arguments.update(overrides)
    return dashboard.estimate_progress(**arguments)


def worktree(worktree_id, **overrides):
    value = {
        "id": worktree_id,
        "repo": "acme/dashboard",
        "branch": "refs/heads/feat/live",
        "displayName": "Dashboard",
        "path": f"/tmp/{worktree_id}",
        "agents": [],
        "liveTerminalCount": 0,
        "pr": None,
        "comment": None,
        "workspaceStatus": "clean",
    }
    value.update(overrides)
    return value


def agent(tab_id, leaf_id, **overrides):
    value = {
        "tabId": tab_id,
        "leafId": leaf_id,
        "state": "done",
        "mainAgent": {"state": "done"},
        "agentType": "codex",
        "prompt": None,
        "lastAssistantMessage": None,
        "updatedAt": NOW_MS - 10_000,
    }
    value.update(overrides)
    return value


def terminal(handle, pane_key, **overrides):
    value = {
        "handle": handle,
        "paneKey": pane_key,
        "title": "✳ Dashboard agent",
        "lastOutputAt": NOW_MS - 1_000,
        "toolName": "Claude Code",
    }
    value.update(overrides)
    return value


print("상수")
expect_equal(
    "STATUS_ORDER 고정",
    lambda: dashboard.STATUS_ORDER,
    ("blocked", "waiting_user", "stale", "running", "background", "idle"),
)
expect_equal("STALE_AFTER_MS = 15분", lambda: dashboard.STALE_AFTER_MS, 900_000)
expect_equal("ERROR_WINDOW_LINES = 15", lambda: dashboard.ERROR_WINDOW_LINES, 15)
expect_predicate(
    "AGENT_TITLE_GLYPHS 필수 글리프 포함",
    lambda: dashboard.AGENT_TITLE_GLYPHS,
    lambda value: set("✳◐◑◒◓✻✢✶") <= set(value),
    "all required glyphs",
)
expect_equal(
    "PIPELINE_KEYWORDS 로드맵 매핑",
    lambda: dashboard.PIPELINE_KEYWORDS,
    {"로드맵": "private-roadmap"},
)

print("clean_title")
for glyph in ("✳", "◐", "◑"):
    expect_equal(
        f"앞 글리프 {glyph} 제거",
        lambda glyph=glyph: dashboard.clean_title(f"{glyph} GRT-9608 작업"),
        "GRT-9608 작업",
    )
expect_equal(
    "문자·점·슬래시로 시작하는 제목 보존",
    lambda: dashboard.clean_title("..pace/greeting"),
    "..pace/greeting",
)
for label, title in (("None", None), ("빈 문자열", ""), ("글리프만", "✳ ◐")):
    expect_equal(f"{label} 제목은 None", lambda title=title: dashboard.clean_title(title), None)

print("extract_recap")
expect_equal(
    "한 줄 recap 과 설정 꼬리 제거",
    lambda: dashboard.extract_recap(
        ["※ recap: 세션 수집 완료 (disable recaps in /config)"]
    ),
    "세션 수집 완료",
)
expect_equal(
    "들여쓰기 연속 2줄 합치기",
    lambda: dashboard.extract_recap(
        ["※ recap: 첫 줄", "  둘째 줄", "\t셋째 줄", "다른 출력"]
    ),
    "첫 줄 둘째 줄 셋째 줄",
)
expect_equal(
    "recap 이 2개면 마지막 것",
    lambda: dashboard.extract_recap(
        ["※ recap: 오래된 요약", "─", "  ※ recap: 최신 요약"]
    ),
    "최신 요약",
)
expect_equal(
    "recap 다음 응답 줄은 제외",
    lambda: dashboard.extract_recap(["※ recap: 요약", "  ⏺ 새 응답"]),
    "요약",
)
expect_equal("recap 없으면 None", lambda: dashboard.extract_recap(["⏺ 응답"]), None)

print("last_reply_from_tail · is_tail_working · summarize")
expect_equal(
    "마지막 ⏺ 응답 블록 추출",
    lambda: dashboard.last_reply_from_tail(
        ["⏺ 이전", "이전 계속", "✻ done", "⏺ 마지막", "계속", "❯ prompt"]
    ),
    "마지막\n계속",
)
expect_equal(
    "⏺ 응답 없으면 None", lambda: dashboard.last_reply_from_tail(["✻ done"]), None
)
expect_equal(
    "최근 8줄의 스피너는 작업 중",
    lambda: dashboard.is_tail_working(
        ["old"] * 8 + ["✢ Waddling… (13s · ↓ 826 tokens)"]
    ),
    True,
)
expect_equal(
    "done 스피너 줄은 작업 중 아님",
    lambda: dashboard.is_tail_working(["✻ Worked for 44s · done 5:44 PM"]),
    False,
)
expect_equal(
    "신선한 recap 우선",
    lambda: dashboard.summarize(["※ recap: 요약"], "마지막 메시지"),
    {"text": "요약", "source": "recap"},
)
expect_equal(
    "recap 이후 응답이면 lastMessage 우선",
    lambda: dashboard.summarize(["※ recap: 낡은 요약", "⏺ 새 응답"], "\n최신 메시지\n둘째 줄"),
    {"text": "최신 메시지", "source": "lastMessage"},
)
expect_equal(
    "요약과 메시지가 모두 없으면 None",
    lambda: dashboard.summarize([], None),
    {"text": None, "source": None},
)

print("parse_step_headings · estimate_progress")
roadmap_markdown = "\n".join(
    ["# roadmap"]
    + [f"## Step {number} — stage" for number in range(9)]
    + ["### Step 10 — excluded", "## Step 4 — duplicate"]
)
expect_equal(
    "roadmap Step 0~8 순서·중복 제거와 ### 제외",
    lambda: dashboard.parse_step_headings(roadmap_markdown),
    ROADMAP_STEPS,
)
expect_equal(
    "코멘트 진행 70% 최우선",
    lambda: progress_result(
        comment="상태: 진행 70%", texts=["/private-roadmap Step 4"]
    ),
    {"percent": 70, "basis": "worktree 코멘트: 진행 70%"},
)
expect_equal(
    "코멘트 진행 101% 무시",
    lambda: progress_result(comment="진행 101%"),
    {"percent": None, "basis": "산정 불가"},
)
expect_equal(
    "done 의 머지 완료 보고는 100%",
    lambda: progress_result(agent_state="done", texts=["squash 머지했습니다"]),
    {"percent": 100, "basis": "완료 보고"},
)
expect_equal(
    "working 의 머지 문구는 100% 아님",
    lambda: progress_result(agent_state="working", texts=["squash 머지했습니다"]),
    {"percent": None, "basis": "산정 불가"},
)
expect_predicate(
    "private-roadmap Step 4 는 44%와 근거",
    lambda: progress_result(texts=["/private-roadmap Step 4 진행 중"]),
    lambda value: value.get("percent") == 44
    and "private-roadmap" in value.get("basis", "")
    and "Step 4" in value.get("basis", ""),
    "44% with private-roadmap and Step 4 basis",
)
expect_equal(
    "로드맵 키워드 Step 2 는 22%",
    lambda: progress_result(texts=["로드맵 Step 2 진행 중"])["percent"],
    22,
)
expect_equal(
    "뒤 텍스트의 Step 6 채택",
    lambda: progress_result(
        texts=["/private-roadmap Step 4 진행 중", "현재 Step 6 수행"]
    )["percent"],
    67,
)
expect_equal(
    "헤딩에 없는 Step 12 는 산정 불가",
    lambda: progress_result(texts=["/private-roadmap Step 12"]),
    {"percent": None, "basis": "산정 불가"},
)
expect_equal(
    "미등록 private-foo 는 산정 불가",
    lambda: progress_result(texts=["/private-foo Step 2"]),
    {"percent": None, "basis": "산정 불가"},
)
expect_equal(
    "진행 근거가 없으면 산정 불가",
    lambda: progress_result(texts=["작업 중"]),
    {"percent": None, "basis": "산정 불가"},
)

print("classify_status")
expect_predicate(
    "미지 state permission 은 사용자 대기",
    lambda: status_result(
        agent_state="permission", last_message="권한을 승인해 주세요."
    ),
    lambda value: value["status"] == "waiting_user" and "승인" in value["reason"],
    "waiting_user with the request sentence",
)
expect_predicate(
    "멈춘 done + BUILD FAILED 는 blocked",
    lambda: status_result(tail_lines=["BUILD FAILED in 3s"]),
    lambda value: value["status"] == "blocked" and "BUILD FAILED" in value["reason"],
    "blocked quoting BUILD FAILED",
)
expect_predicate(
    "working + 최근 FAILED 는 running 과 최근 실패 사유",
    lambda: status_result(agent_state="working", tail_lines=["task FAILED"]),
    lambda value: value["status"] == "running"
    and value["reason"].startswith("최근 실패 출력:")
    and "FAILED" in value["reason"],
    "running with recent failure reason",
)
expect_equal(
    "working 20분 무출력 + FAILED 는 blocked",
    lambda: status_result(
        agent_state="working",
        tail_lines=["Traceback (most recent call last):"],
        last_output_at=NOW_MS - 1_200_000,
    )["status"],
    "blocked",
)
for label, line in (
    ("FAILED_TO_SEND", "FAILED_TO_SEND    1    0"),
    ("ERROR 표", "│ ERROR │ 5개 서비스 모두 0건 │"),
    ("exit code 0", "completed (exit code 0)"),
):
    expect_equal(
        f"{label} 오탐 금지",
        lambda line=line: status_result(tail_lines=[line])["status"],
        "idle",
    )
expect_equal(
    "마지막 15줄 밖 FAILED 무시",
    lambda: status_result(
        tail_lines=["BUILD FAILED"] + [f"normal {number}" for number in range(15)]
    )["status"],
    "idle",
)
expect_equal(
    "working 정확히 15분 무출력은 stale",
    lambda: status_result(
        agent_state="working", last_output_at=NOW_MS - 900_000
    )["status"],
    "stale",
)
expect_equal(
    "working 14분59초 무출력은 running",
    lambda: status_result(
        agent_state="working", last_output_at=NOW_MS - 899_000
    )["status"],
    "running",
)
expect_equal(
    "working + lastOutputAt None 은 running",
    lambda: status_result(agent_state="working", last_output_at=None)["status"],
    "running",
)
expect_equal(
    "working + mainAgent done 은 background",
    lambda: status_result(agent_state="working", main_state="done")["status"],
    "background",
)
expect_predicate(
    "done + 지시하시면 은 사용자 대기와 문장 인용",
    lambda: status_result(
        last_message="현재 작업은 끝났습니다. 지시하시면 다음 단계를 진행합니다."
    ),
    lambda value: value["status"] == "waiting_user"
    and value["reason"] == "지시하시면 다음 단계를 진행합니다.",
    "waiting_user quoting only the request sentence",
)
expect_equal(
    "done + 할까요? 는 사용자 대기",
    lambda: status_result(last_message="다음 단계도 할까요?")["status"],
    "waiting_user",
)
expect_equal(
    "승인을 요청할게요 예고는 대기 아님",
    lambda: status_result(last_message="곧 승인을 요청할게요.")["status"],
    "idle",
)
for count, noun in ((1, "shell"), (2, "shells")):
    expect_predicate(
        f"마지막 상태 줄의 {count} {noun} still running 은 background",
        lambda count=count, noun=noun: status_result(
            tail_lines=[f"✻ {count} {noun} still running"]
        ),
        lambda value, count=count: value["status"] == "background"
        and str(count) in value["reason"],
        "background with shell count",
    )
expect_equal(
    "오래된 shell running 뒤 새 done 상태 줄이면 background 아님",
    lambda: status_result(
        tail_lines=["✻ 1 shell still running", "✻ Worked for 3s · done"]
    )["status"],
    "idle",
)
expect_equal(
    "done 신호 없음은 idle",
    lambda: status_result()["status"],
    "idle",
)

print("build_snapshot")
joined_worktree = worktree(
    "wt-joined",
    displayName="Fallback name",
    agents=[
        agent(
            "tab-a",
            "leaf-a",
            state="working",
            mainAgent={"state": "working"},
            prompt="/private-roadmap Step 4",
            lastAssistantMessage="작업 중",
        )
    ],
    liveTerminalCount=1,
    pr={"number": 42, "state": "OPEN"},
    comment="진행 70%",
    workspaceStatus="modified",
)
joined_terminal = terminal(
    "term-a", "tab-a:leaf-a", title="✳ Joined agent", lastOutputAt=NOW_MS - 2_000
)
expect_equal(
    "paneKey 조인·이름·branch·PR·공개 필드 매핑",
    lambda: {
        key: dashboard.build_snapshot(
            [joined_worktree],
            [joined_terminal],
            {"term-a": ["※ recap: 수집 중"]},
            now_ms=NOW_MS,
            pipelines=PIPELINES,
        )["sessions"][0][key]
        for key in (
            "id",
            "kind",
            "name",
            "worktreeId",
            "repo",
            "branch",
            "terminalHandle",
            "agentType",
            "agentState",
            "mainState",
            "toolName",
            "lastOutputAt",
            "idleSeconds",
            "pr",
            "comment",
            "workspaceStatus",
        )
    },
    {
        "id": "tab-a:leaf-a",
        "kind": "agent",
        "name": "Joined agent",
        "worktreeId": "wt-joined",
        "repo": "acme/dashboard",
        "branch": "feat/live",
        "terminalHandle": "term-a",
        "agentType": "codex",
        "agentState": "working",
        "mainState": "working",
        "toolName": "Claude Code",
        "lastOutputAt": NOW_MS - 2_000,
        "idleSeconds": 2,
        "pr": {"number": 42, "state": "OPEN"},
        "comment": "진행 70%",
        "workspaceStatus": "modified",
    },
)
fallback_worktree = worktree(
    "wt-fallback",
    displayName="Fallback name",
    branch="",
    agents=[agent("tab-b", "leaf-b", updatedAt=NOW_MS - 3_000)],
)
expect_equal(
    "터미널 조인 실패 agent 는 displayName·updatedAt·detached 사용",
    lambda: {
        key: dashboard.build_snapshot(
            [fallback_worktree], [], {}, now_ms=NOW_MS, pipelines=PIPELINES
        )["sessions"][0][key]
        for key in ("name", "branch", "terminalHandle", "lastOutputAt", "pr")
    },
    {
        "name": "Fallback name",
        "branch": "(detached)",
        "terminalHandle": None,
        "lastOutputAt": NOW_MS - 3_000,
        "pr": None,
    },
)
terminal_worktree = worktree("wt-terminal", liveTerminalCount=2)
unjoined_agent_terminal = terminal(
    "term-glyph",
    "tab-x:leaf-x",
    title="✳ GRT-9608 하위 테스트 티켓 작성",
    worktreeId="wt-terminal",
)
plain_shell_terminal = terminal(
    "term-shell",
    "tab-y:leaf-y",
    title=None,
    worktreeId="wt-terminal",
)
expect_equal(
    "agents 미등록 글리프 터미널은 terminal 세션, 일반 셸은 제외",
    lambda: [
        {
            key: session[key]
            for key in ("id", "kind", "name", "worktreeId", "agentType", "summary")
        }
        for session in dashboard.build_snapshot(
            [terminal_worktree],
            [unjoined_agent_terminal, plain_shell_terminal],
            {"term-glyph": ["⏺ 마지막 응답"], "term-shell": []},
            now_ms=NOW_MS,
            pipelines=PIPELINES,
        )["sessions"]
    ],
    [
        {
            "id": "term-glyph",
            "kind": "terminal",
            "name": "GRT-9608 하위 테스트 티켓 작성",
            "worktreeId": "wt-terminal",
            "agentType": None,
            "summary": {"text": "마지막 응답", "source": "lastMessage"},
        }
    ],
)
empty_worktrees = [
    worktree("wt-shell-only", liveTerminalCount=1),
    worktree("wt-no-terminal", liveTerminalCount=0),
    worktree("wt-archived", isArchived=True, liveTerminalCount=0),
]
expect_equal(
    "세션 없는 worktree 는 shellOnly·noTerminal 분리하고 archived 제외",
    lambda: {
        "shellOnly": [item["worktreeId"] for item in dashboard.build_snapshot(
            empty_worktrees, [], {}, now_ms=NOW_MS, pipelines=PIPELINES
        )["shellOnly"]],
        "noTerminal": [item["worktreeId"] for item in dashboard.build_snapshot(
            empty_worktrees, [], {}, now_ms=NOW_MS, pipelines=PIPELINES
        )["noTerminal"]],
    },
    {"shellOnly": ["wt-shell-only"], "noTerminal": ["wt-no-terminal"]},
)

status_agents = [
    agent("tab-blocked", "leaf", state="done"),
    agent("tab-waiting", "leaf", state="permission"),
    agent("tab-stale", "leaf", state="working", mainAgent={"state": "working"}),
    agent("tab-running", "leaf", state="working", mainAgent={"state": "working"}),
    agent("tab-background", "leaf", state="working", mainAgent={"state": "done"}),
    agent("tab-idle-old", "leaf", state="done"),
    agent("tab-idle-new", "leaf", state="done"),
]
status_terminals = [
    terminal("h-blocked", "tab-blocked:leaf", lastOutputAt=NOW_MS - 1_000),
    terminal("h-waiting", "tab-waiting:leaf", lastOutputAt=NOW_MS - 2_000),
    terminal("h-stale", "tab-stale:leaf", lastOutputAt=NOW_MS - 900_000),
    terminal("h-running", "tab-running:leaf", lastOutputAt=NOW_MS - 3_000),
    terminal("h-background", "tab-background:leaf", lastOutputAt=NOW_MS - 4_000),
    terminal("h-idle-old", "tab-idle-old:leaf", lastOutputAt=NOW_MS - 20_000),
    terminal("h-idle-new", "tab-idle-new:leaf", lastOutputAt=NOW_MS - 10_000),
]
status_tails = {terminal_value["handle"]: [] for terminal_value in status_terminals}
status_tails["h-blocked"] = ["BUILD FAILED"]
status_snapshot_arguments = (
    [worktree("wt-status", agents=status_agents, liveTerminalCount=7)],
    status_terminals,
    status_tails,
)
expect_equal(
    "STATUS_ORDER 와 같은 상태 lastOutputAt 내림차순 정렬",
    lambda: [
        (session["status"], session["id"])
        for session in dashboard.build_snapshot(
            *status_snapshot_arguments, now_ms=NOW_MS, pipelines=PIPELINES
        )["sessions"]
    ],
    [
        ("blocked", "tab-blocked:leaf"),
        ("waiting_user", "tab-waiting:leaf"),
        ("stale", "tab-stale:leaf"),
        ("running", "tab-running:leaf"),
        ("background", "tab-background:leaf"),
        ("idle", "tab-idle-new:leaf"),
        ("idle", "tab-idle-old:leaf"),
    ],
)
expect_equal(
    "KPI 는 background 를 실행 중, blocked+stale 를 막힘/정체로 집계",
    lambda: dashboard.build_snapshot(
        *status_snapshot_arguments, now_ms=NOW_MS, pipelines=PIPELINES
    )["kpi"],
    {"total": 7, "running": 2, "waitingUser": 1, "blockedOrStale": 2},
)

print("orca_command")
expect_equal(
    "ORCA_CLI_COMMAND 는 shlex.split",
    lambda: dashboard.orca_command(
        {"ORCA_CLI_COMMAND": 'python3 "/tmp/orca fixture.py" --mode test'}
    ),
    ["python3", "/tmp/orca fixture.py", "--mode", "test"],
)
expect_equal("ORCA_CLI_COMMAND 미설정은 orca", lambda: dashboard.orca_command({}), ["orca"])


ORCA_STUB = r'''#!/usr/bin/env python3
import json
import sys

arguments = sys.argv[1:]
if arguments[-1:] == ["--json"]:
    arguments = arguments[:-1]

if arguments == ["worktree", "ps"]:
    result = {"worktrees": []}
elif arguments == ["terminal", "list"]:
    result = {"terminals": []}
elif arguments[:2] == ["terminal", "read"]:
    result = {"terminal": {"tail": []}}
else:
    print(json.dumps({"ok": False, "error": "unexpected arguments: " + repr(arguments)}))
    raise SystemExit(1)

print(json.dumps({"ok": True, "result": result}))
'''


def fixture_environment(directory):
    stub_path = Path(directory) / "orca fixture.py"
    stub_path.write_text(ORCA_STUB, encoding="utf-8")
    environment = os.environ.copy()
    environment["ORCA_CLI_COMMAND"] = shlex.join([sys.executable, str(stub_path)])
    return environment


def parse_stdout_json(process):
    try:
        return json.loads(process.stdout)
    except (TypeError, json.JSONDecodeError):
        return None


print("CLI")
no_args = subprocess.run(
    [sys.executable, str(DASHBOARD_PATH)],
    cwd=ROOT,
    capture_output=True,
    text=True,
    timeout=10,
)
check(
    "인자 없음은 stderr usage + exit 2",
    no_args.returncode == 2 and "usage" in no_args.stderr.lower(),
    f"exit={no_args.returncode}, stderr={no_args.stderr[-400:]!r}",
)

with tempfile.TemporaryDirectory(prefix="orca dashboard ") as temporary_directory:
    fixture_env = fixture_environment(temporary_directory)
    snapshot_process = subprocess.run(
        [sys.executable, str(DASHBOARD_PATH), "snapshot"],
        cwd=ROOT,
        env=fixture_env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    snapshot_payload = parse_stdout_json(snapshot_process)
    check(
        "스텁 Orca snapshot 은 exit 0 + 유효 snapshot JSON",
        snapshot_process.returncode == 0
        and isinstance(snapshot_payload, dict)
        and snapshot_payload.get("sessions") == []
        and snapshot_payload.get("error") is None,
        "exit={} stdout={!r} stderr={!r}".format(
            snapshot_process.returncode,
            snapshot_process.stdout[-500:],
            snapshot_process.stderr[-500:],
        ),
    )

failure_env = os.environ.copy()
failure_env["ORCA_CLI_COMMAND"] = "false"
failure_process = subprocess.run(
    [sys.executable, str(DASHBOARD_PATH), "snapshot"],
    cwd=ROOT,
    env=failure_env,
    capture_output=True,
    text=True,
    timeout=10,
)
failure_payload = parse_stdout_json(failure_process)
check(
    "Orca 실패 snapshot 은 exit 1 + error JSON",
    failure_process.returncode == 1
    and isinstance(failure_payload, dict)
    and bool(failure_payload.get("error")),
    "exit={} stdout={!r} stderr={!r}".format(
        failure_process.returncode,
        failure_process.stdout[-500:],
        failure_process.stderr[-500:],
    ),
)


def unused_local_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def http_response(url):
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            return response.status, response.headers, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read().decode("utf-8")


print("serve")
with tempfile.TemporaryDirectory(prefix="orca dashboard serve ") as temporary_directory:
    serve_env = fixture_environment(temporary_directory)
    port = unused_local_port()
    serve_process = subprocess.Popen(
        [
            sys.executable,
            str(DASHBOARD_PATH),
            "serve",
            "--port",
            str(port),
            "--interval",
            "0.1",
        ],
        cwd=ROOT,
        env=serve_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    responses = None
    serve_error = "server did not become ready"
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if serve_process.poll() is not None:
                stderr = serve_process.stderr.read() if serve_process.stderr else ""
                serve_error = f"server exited {serve_process.returncode}: {stderr[-800:]}"
                break
            try:
                responses = {
                    "snapshot": http_response(f"http://127.0.0.1:{port}/api/snapshot"),
                    "root": http_response(f"http://127.0.0.1:{port}/"),
                    "missing": http_response(f"http://127.0.0.1:{port}/nope"),
                }
                break
            except (OSError, TimeoutError):
                time.sleep(0.05)
    finally:
        if serve_process.poll() is None:
            serve_process.terminate()
            try:
                serve_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                serve_process.kill()
                serve_process.wait(timeout=3)

    check("serve 가 빈 포트에서 기동", responses is not None, serve_error)
    if responses is not None:
        snapshot_status, snapshot_headers, snapshot_body = responses["snapshot"]
        try:
            served_snapshot = json.loads(snapshot_body)
        except json.JSONDecodeError:
            served_snapshot = None
        check(
            "/api/snapshot 은 200 JSON 과 sessions",
            snapshot_status == 200
            and snapshot_headers.get_content_type() == "application/json"
            and isinstance(served_snapshot, dict)
            and "sessions" in served_snapshot
            and served_snapshot.get("interval") == 0.1
            and "lastSuccessAt" in served_snapshot,
            f"status={snapshot_status}, headers={dict(snapshot_headers)}, body={snapshot_body[:500]!r}",
        )
        root_status, root_headers, root_body = responses["root"]
        check(
            "/ 는 200 HTML 과 라이트·다크 토큰",
            root_status == 200
            and root_headers.get_content_type() == "text/html"
            and "prefers-color-scheme" in root_body,
            f"status={root_status}, headers={dict(root_headers)}, body={root_body[:500]!r}",
        )
        check("알 수 없는 HTTP 경로는 404", responses["missing"][0] == 404)

print()
if failures:
    print(f"실패 {len(failures)}건")
    sys.exit(1)
print("전부 통과")
