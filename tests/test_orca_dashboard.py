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
import re
import shlex
import shutil
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


def expect_exception(name, action, expected_type):
    try:
        action()
    except Exception as error:
        check(
            name,
            isinstance(error, expected_type),
            f"expected {expected_type.__name__}, actual={type(error).__name__}: {error}",
        )
        return
    check(name, False, f"expected {expected_type.__name__}, but no exception was raised")


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
        "worktreeId": worktree_id,
        "repoId": "repo-acme-dashboard",
        "repo": "acme/dashboard",
        "branch": "refs/heads/feat/live",
        "displayName": "Dashboard",
        "path": f"/tmp/{worktree_id}",
        "isArchived": False,
        "agents": [],
        "liveTerminalCount": 0,
        "lastOutputAt": NOW_MS - 1_000,
        "linkedPR": None,
        "comment": None,
        "workspaceStatus": "clean",
    }
    value.update(overrides)
    return value


def agent(pane_key, **overrides):
    value = {
        "paneKey": pane_key,
        "parentPaneKey": None,
        "state": "done",
        "mainAgent": {"state": "done"},
        "agentType": "codex",
        "prompt": None,
        "lastAssistantMessage": None,
        "toolName": "Claude Code",
        "toolInput": None,
        "interrupted": False,
        "stateStartedAt": NOW_MS - 20_000,
        "updatedAt": NOW_MS - 10_000,
    }
    value.update(overrides)
    return value


def terminal(handle, worktree_id, tab_id, leaf_id, **overrides):
    value = {
        "handle": handle,
        "worktreeId": worktree_id,
        "worktreePath": f"/tmp/{worktree_id}",
        "branch": "refs/heads/feat/live",
        "tabId": tab_id,
        "leafId": leaf_id,
        "title": "✳ Dashboard agent",
        "connected": True,
        "lastOutputAt": NOW_MS - 1_000,
        "preview": "",
    }
    value.update(overrides)
    return value


def snapshot_progress(last_message, tail_lines, state="done"):
    progress_worktree = worktree(
        "wt-progress",
        agents=[
            agent(
                "tab-progress:leaf",
                state=state,
                prompt="/private-roadmap",
                lastAssistantMessage=last_message,
            )
        ],
        liveTerminalCount=1,
    )
    progress_terminal = terminal(
        "term-progress", "wt-progress", "tab-progress", "leaf"
    )
    return dashboard.build_snapshot(
        [progress_worktree],
        [progress_terminal],
        {"term-progress": tail_lines},
        now_ms=NOW_MS,
        pipelines=PIPELINES,
    )["sessions"][0]["progress"]


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
expect_equal(
    "코드 펜스로 시작한 lastMessage 는 첫 의미 있는 줄을 요약",
    lambda: dashboard.summarize([], "```json\n\n# **수집 결과**\n```"),
    {"text": "수집 결과", "source": "lastMessage"},
)
expect_equal(
    "마크다운 표 행을 건너뛰고 기호를 제거한 줄을 요약",
    lambda: dashboard.summarize(
        [], "| 항목 | 값 |\n|---|---|\n> - **실행 결과**"
    ),
    {"text": "실행 결과", "source": "lastMessage"},
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

print("parse_step_titles")
expect_equal(
    "Step 제목의 em dash 구분자 제거",
    lambda: dashboard.parse_step_titles("## Step 4 — 로드맵"),
    {4: "로드맵"},
)
expect_equal(
    "Step 제목의 colon 구분자 제거",
    lambda: dashboard.parse_step_titles("## Step 2: RED 테스트"),
    {2: "RED 테스트"},
)
expect_equal(
    "구분자 없는 Step 제목 추출",
    lambda: dashboard.parse_step_titles("## Step 6 구현"),
    {6: "구현"},
)
expect_equal(
    "제목 없는 Step 은 빈 문자열",
    lambda: dashboard.parse_step_titles("## Step 3"),
    {3: ""},
)
expect_equal(
    "중복 Step 번호는 첫 헤딩 제목 우선",
    lambda: dashboard.parse_step_titles(
        "## Step 1 - 첫 제목\n## Step 1 – 나중 제목\n### Step 2 — 제외"
    ),
    {1: "첫 제목"},
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
    "done 의 여러 줄 완료 보고는 전체 원문을 검사해 100%",
    lambda: progress_result(
        agent_state="done", texts=["검증 결과입니다.\n모든 작업을 완료했습니다."]
    ),
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
    "현재 Step 과 다음 Step 이 함께 있으면 예고를 제외",
    lambda: progress_result(
        texts=[
            "/private-roadmap 현재 Step 4 진행 중입니다. 다음은 Step 8입니다."
        ]
    )["percent"],
    44,
)
expect_equal(
    "Step 뒤에 다음 단계 표현이 있어도 현재 Step 만 채택",
    lambda: progress_result(
        texts=[
            "/private-roadmap 현재 Step 4 진행 중입니다. Step 8은 다음 단계입니다."
        ]
    )["percent"],
    44,
)
expect_equal(
    "예고 문장에만 Step 이 있으면 산정 불가",
    lambda: progress_result(
        texts=["/private-roadmap Step 8 은 이후 진행"]
    ),
    {"percent": None, "basis": "산정 불가"},
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

print("pipeline_checklist")
roadmap_titles = {
    number: f"단계 {number}" for number in ROADMAP_STEPS
}
expect_equal(
    "Step 6/9 체크리스트는 done 6개·current 1개·pending 2개와 제목",
    lambda: dashboard.pipeline_checklist(
        agent_state="working",
        texts=["/private-roadmap Step 6 진행 중"],
        pipelines=PIPELINES,
        step_titles={"private-roadmap": roadmap_titles},
    ),
    {
        "pipeline": "private-roadmap",
        "steps": [
            {
                "number": number,
                "title": f"단계 {number}",
                "state": "done" if number < 6 else "current" if number == 6 else "pending",
            }
            for number in ROADMAP_STEPS
        ],
    },
)
expect_equal(
    "체크리스트 현재 Step 판정은 예고 문장의 Step 을 제외",
    lambda: dashboard.pipeline_checklist(
        agent_state="working",
        texts=[
            "/private-roadmap 현재 Step 4 진행 중입니다. Step 8은 다음 단계입니다."
        ],
        pipelines=PIPELINES,
        step_titles={"private-roadmap": roadmap_titles},
    )["steps"][4]["state"],
    "current",
)
expect_equal(
    "파이프라인을 탐지하지 못하면 체크리스트 없음",
    lambda: dashboard.pipeline_checklist(
        agent_state="working",
        texts=["Step 4 진행 중"],
        pipelines=PIPELINES,
    ),
    None,
)
expect_equal(
    "현재 Step 이 파이프라인 목록에 없으면 체크리스트 없음",
    lambda: dashboard.pipeline_checklist(
        agent_state="working",
        texts=["/private-roadmap Step 12 진행 중"],
        pipelines=PIPELINES,
    ),
    None,
)
expect_predicate(
    "done + 완료 보고면 체크리스트 전 단계 done",
    lambda: dashboard.pipeline_checklist(
        agent_state="done",
        texts=[
            "/private-roadmap Step 6 검증 결과입니다.\n모든 작업을 완료했습니다."
        ],
        pipelines=PIPELINES,
        step_titles={"private-roadmap": roadmap_titles},
    ),
    lambda value: value is not None
    and len(value["steps"]) == 9
    and all(step["state"] == "done" for step in value["steps"]),
    "nine done steps",
)
expect_predicate(
    "step_titles 미전달 시 모든 제목은 빈 문자열",
    lambda: dashboard.pipeline_checklist(
        agent_state="working",
        texts=["/private-roadmap Step 0 진행 중"],
        pipelines=PIPELINES,
    ),
    lambda value: value is not None
    and all(step["title"] == "" for step in value["steps"]),
    "all titles empty",
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
            "tab-a:leaf-a",
            state="working",
            mainAgent={"state": "working"},
            prompt="/private-roadmap Step 4",
            lastAssistantMessage="작업 중",
        )
    ],
    liveTerminalCount=1,
    linkedPR={"number": 42, "state": "OPEN"},
    comment="진행 70%",
    workspaceStatus="modified",
)
joined_terminal = terminal(
    "term-a",
    "wt-joined",
    "tab-a",
    "leaf-a",
    title="✳ Joined agent",
    lastOutputAt=NOW_MS - 2_000,
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
    agents=[agent("tab-b:leaf-b", updatedAt=NOW_MS - 3_000)],
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
    "wt-terminal",
    "tab-x",
    "leaf-x",
    title="✳ GRT-9608 하위 테스트 티켓 작성",
)
plain_shell_terminal = terminal(
    "term-shell",
    "wt-terminal",
    "pty:5150a2fa@@a68bac86",
    "shell",
    title=None,
    lastOutputAt=None,
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
    agent("tab-blocked:leaf", state="done"),
    agent("tab-waiting:leaf", state="permission"),
    agent("tab-stale:leaf", state="working", mainAgent={"state": "working"}),
    agent("tab-running:leaf", state="working", mainAgent={"state": "working"}),
    agent("tab-background:leaf", state="working", mainAgent={"state": "done"}),
    agent("tab-idle-old:leaf", state="done"),
    agent("tab-idle-new:leaf", state="done"),
]
status_terminals = [
    terminal("h-blocked", "wt-status", "tab-blocked", "leaf", lastOutputAt=NOW_MS - 1_000),
    terminal("h-waiting", "wt-status", "tab-waiting", "leaf", lastOutputAt=NOW_MS - 2_000),
    terminal("h-stale", "wt-status", "tab-stale", "leaf", lastOutputAt=NOW_MS - 900_000),
    terminal("h-running", "wt-status", "tab-running", "leaf", lastOutputAt=NOW_MS - 3_000),
    terminal("h-background", "wt-status", "tab-background", "leaf", lastOutputAt=NOW_MS - 4_000),
    terminal("h-idle-old", "wt-status", "tab-idle-old", "leaf", lastOutputAt=NOW_MS - 20_000),
    terminal("h-idle-new", "wt-status", "tab-idle-new", "leaf", lastOutputAt=NOW_MS - 10_000),
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

completion_worktree = worktree(
    "wt-completion",
    agents=[
        agent(
            "tab-completion:leaf",
            state="done",
            lastAssistantMessage="검증 결과입니다.\n모든 작업을 완료했습니다.",
        )
    ],
    liveTerminalCount=1,
)
completion_terminal = terminal(
    "term-completion", "wt-completion", "tab-completion", "leaf"
)
expect_equal(
    "build_snapshot 도 여러 줄 완료 원문으로 100% 판정",
    lambda: dashboard.build_snapshot(
        [completion_worktree],
        [completion_terminal],
        {"term-completion": []},
        now_ms=NOW_MS,
        pipelines=PIPELINES,
    )["sessions"][0]["progress"],
    {"percent": 100, "basis": "완료 보고"},
)
expect_equal(
    "build_snapshot 은 낡은 Step 4 recap 보다 최신 완료 보고를 채택",
    lambda: snapshot_progress(
        "검증 결과입니다.\n모든 작업을 완료했습니다.",
        ["※ recap: Step 4 진행 중", "⏺ 모든 작업을 완료했습니다."],
    ),
    {"percent": 100, "basis": "완료 보고"},
)
expect_equal(
    "build_snapshot 은 낡은 Step 4 recap 보다 최신 Step 6을 채택",
    lambda: snapshot_progress(
        "/private-roadmap Step 6 진행 중",
        ["※ recap: Step 4 진행 중", "⏺ Step 6 진행 중"],
    ),
    {
        "percent": 67,
        "basis": "/private-roadmap Step 6 (7/9단계 진행 중)",
    },
)
expect_equal(
    "build_snapshot 은 신선한 Step 6 recap 을 이전 Step 4 메시지보다 우선",
    lambda: snapshot_progress(
        "/private-roadmap Step 4 진행 중",
        ["※ recap: Step 6 진행 중"],
    ),
    {
        "percent": 67,
        "basis": "/private-roadmap Step 6 (7/9단계 진행 중)",
    },
)

tail_error_worktree = worktree(
    "wt-tail-error",
    agents=[agent("tab-tail-error:leaf", state="done")],
    liveTerminalCount=1,
)
tail_error_terminal = terminal(
    "term-tail-error", "wt-tail-error", "tab-tail-error", "leaf"
)
expect_equal(
    "terminal read 실패 세션은 stale 이고 snapshot warning 을 노출",
    lambda: {
        "warnings": snapshot["warnings"],
        "status": snapshot["sessions"][0]["status"],
        "reason": snapshot["sessions"][0]["reason"],
    }
    if (
        snapshot := dashboard.build_snapshot(
            [tail_error_worktree],
            [tail_error_terminal],
            {"term-tail-error": []},
            now_ms=NOW_MS,
            pipelines=PIPELINES,
            tail_errors={"term-tail-error": "permission denied"},
        )
    )
    else None,
    {
        "warnings": [
            "terminal read 실패 term-tail-error: permission denied"
        ],
        "status": "stale",
        "reason": "화면 읽기 실패 — 상태 판정 불가: permission denied",
    },
)

checklist_worktree = worktree(
    "wt-checklist",
    agents=[
        agent(
            "tab-checklist:leaf",
            state="working",
            mainAgent={"state": "working"},
            prompt="/private-roadmap Step 6 진행 중",
        )
    ],
    liveTerminalCount=1,
)
checklist_terminal = terminal(
    "term-checklist", "wt-checklist", "tab-checklist", "leaf"
)
expect_predicate(
    "build_snapshot 세션은 근거가 있으면 checklist 를 포함",
    lambda: dashboard.build_snapshot(
        [checklist_worktree],
        [checklist_terminal],
        {"term-checklist": []},
        now_ms=NOW_MS,
        pipelines=PIPELINES,
        step_titles={"private-roadmap": roadmap_titles},
    )["sessions"][0]["checklist"],
    lambda value: value is not None
    and value["pipeline"] == "private-roadmap"
    and value["steps"][6]
    == {"number": 6, "title": "단계 6", "state": "current"},
    "private-roadmap checklist with Step 6 current",
)
expect_equal(
    "build_snapshot 은 step_titles 미전달·근거 없음에도 checklist None 포함",
    lambda: dashboard.build_snapshot(
        [worktree("wt-no-checklist", agents=[agent("tab-none:leaf")])],
        [],
        {},
        now_ms=NOW_MS,
        pipelines=PIPELINES,
    )["sessions"][0]["checklist"],
    None,
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

print("load_pipelines 읽기 실패")
with tempfile.TemporaryDirectory(prefix="orca dashboard skill read ") as temporary_directory:
    skills_directory = Path(temporary_directory) / "skills"
    readable_skill = skills_directory / "private-readable" / "SKILL.md"
    unreadable_skill = skills_directory / "private-unreadable" / "SKILL.md"
    readable_skill.parent.mkdir(parents=True)
    unreadable_skill.parent.mkdir(parents=True)
    readable_skill.write_text("# Skill\n\n## Step 0\n\n## Step 1\n", encoding="utf-8")
    unreadable_skill.write_text("# Secret\n\n## Step 9\n", encoding="utf-8")
    unreadable_skill.chmod(0o000)
    pipeline_warnings = []
    try:
        loaded_pipelines = dashboard.load_pipelines(
            str(skills_directory), pipeline_warnings
        )
        load_pipelines_error = ""
    except Exception as error:
        loaded_pipelines = None
        load_pipelines_error = f"{type(error).__name__}: {error}"
    finally:
        unreadable_skill.chmod(0o600)
    check(
        "권한 없는 SKILL.md 는 건너뛰고 나머지 pipeline 과 warning 반환",
        loaded_pipelines == {"private-readable": [0, 1]}
        and len(pipeline_warnings) == 1
        and pipeline_warnings[0].startswith(
            f"SKILL.md 읽기 실패 {unreadable_skill}: "
        ),
        load_pipelines_error
        or f"pipelines={loaded_pipelines!r}, warnings={pipeline_warnings!r}",
    )

print("load_step_titles 읽기 실패")
with tempfile.TemporaryDirectory(prefix="orca dashboard step titles ") as temporary_directory:
    skills_directory = Path(temporary_directory) / "skills"
    alpha_skill = skills_directory / "private-alpha" / "SKILL.md"
    beta_skill = skills_directory / "private-beta" / "SKILL.md"
    no_steps_skill = skills_directory / "private-no-steps" / "SKILL.md"
    unreadable_skill = skills_directory / "private-unreadable" / "SKILL.md"
    for skill_file in (alpha_skill, beta_skill, no_steps_skill, unreadable_skill):
        skill_file.parent.mkdir(parents=True)
    alpha_skill.write_text(
        "# Alpha\n\n## Step 0 — 준비\n\n## Step 1: 검증\n",
        encoding="utf-8",
    )
    beta_skill.write_text(
        "# Beta\n\n## Step 2 구현\n\n## Step 3\n",
        encoding="utf-8",
    )
    no_steps_skill.write_text("# No steps\n", encoding="utf-8")
    unreadable_skill.write_text(
        "# Unreadable\n\n## Step 9 — 비밀\n", encoding="utf-8"
    )
    unreadable_skill.chmod(0o000)
    title_warnings = []
    try:
        loaded_titles = dashboard.load_step_titles(
            str(skills_directory), title_warnings
        )
        load_titles_error = ""
    except Exception as error:
        loaded_titles = None
        load_titles_error = f"{type(error).__name__}: {error}"
    finally:
        unreadable_skill.chmod(0o600)
    check(
        "정상 스킬 2개 제목만 반환하고 읽기 실패 warning 1줄",
        loaded_titles
        == {
            "private-alpha": {0: "준비", 1: "검증"},
            "private-beta": {2: "구현", 3: ""},
        }
        and len(title_warnings) == 1
        and title_warnings[0].startswith(
            f"SKILL.md 읽기 실패 {unreadable_skill}: "
        ),
        load_titles_error
        or f"titles={loaded_titles!r}, warnings={title_warnings!r}",
    )

print("run_orca 실행 실패")
with tempfile.TemporaryDirectory(prefix="orca dashboard permission ") as temporary_directory:
    non_executable = Path(temporary_directory) / "orca-no-execute"
    non_executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    non_executable.chmod(0o600)
    expect_exception(
        "실행 권한 없는 Orca 파일은 OrcaError",
        lambda: dashboard.run_orca([str(non_executable)], ["worktree", "ps"]),
        dashboard.OrcaError,
    )
expect_exception(
    "없는 Orca 실행 파일은 OrcaError",
    lambda: dashboard.run_orca(
        ["/definitely/missing/orca-dashboard-test-binary"], ["worktree", "ps"]
    ),
    dashboard.OrcaError,
)


ORCA_STUB = r'''#!/usr/bin/env python3
import json
import os
import sys

arguments = sys.argv[1:]
if arguments[-1:] == ["--json"]:
    arguments = arguments[:-1]

cycle_file = os.environ.get("ORCA_STUB_CYCLE_FILE")
if cycle_file and arguments == ["worktree", "ps"]:
    try:
        with open(cycle_file, encoding="utf-8") as handle:
            cycle = int(handle.read()) + 1
    except (FileNotFoundError, ValueError):
        cycle = 1
    with open(cycle_file, "w", encoding="utf-8") as handle:
        handle.write(str(cycle))
    if cycle == 2:
        print(json.dumps({"ok": False, "error": "temporary collection failure"}))
        raise SystemExit(0)

if arguments == ["worktree", "ps"]:
    result = {
        "worktrees": [{
            "worktreeId": "wt-stub",
            "repoId": "repo-stub",
            "repo": "acme/dashboard",
            "displayName": "Stub dashboard",
            "path": "/tmp/wt-stub",
            "branch": "refs/heads/feat/live",
            "isArchived": False,
            "workspaceStatus": "clean",
            "comment": "",
            "liveTerminalCount": 1,
            "lastOutputAt": 1999000,
            "linkedPR": None,
            "agents": [{
                "paneKey": "tab-stub:leaf-stub",
                "parentPaneKey": None,
                "state": "done",
                "agentType": "codex",
                "prompt": "snapshot fixture",
                "lastAssistantMessage": "fixture ready",
                "toolName": "Read",
                "toolInput": "tests/test_orca_dashboard.py",
                "interrupted": False,
                "mainAgent": {"state": "done", "stateStartedAt": 1980000},
                "stateStartedAt": 1985000,
                "updatedAt": 1999000
            }]
        }]
    }
elif arguments == ["terminal", "list"]:
    result = {
        "terminals": [{
            "handle": "term-stub",
            "worktreeId": "wt-stub",
            "worktreePath": "/tmp/wt-stub",
            "branch": "refs/heads/feat/live",
            "tabId": "tab-stub",
            "leafId": "leaf-stub",
            "title": "✳ Stub dashboard",
            "connected": True,
            "lastOutputAt": 1999000,
            "preview": "fixture ready"
        }]
    }
elif arguments[:2] == ["terminal", "read"]:
    if os.environ.get("ORCA_STUB_READ_FAIL"):
        print(json.dumps({"ok": False, "error": os.environ["ORCA_STUB_READ_FAIL"]}))
        raise SystemExit(0)
    result = {
        "terminal": {
            "handle": "term-stub",
            "tail": ["⏺ fixture ready"]
        }
    }
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
    environment["ORCA_DASHBOARD_HISTORY_DIR"] = str(Path(directory) / "history")
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
        and len(snapshot_payload.get("sessions", [])) == 1
        and snapshot_payload["sessions"][0].get("id") == "tab-stub:leaf-stub"
        and snapshot_payload["sessions"][0].get("terminalHandle") == "term-stub"
        and snapshot_payload.get("error") is None,
        "exit={} stdout={!r} stderr={!r}".format(
            snapshot_process.returncode,
            snapshot_process.stdout[-500:],
            snapshot_process.stderr[-500:],
        ),
    )

with tempfile.TemporaryDirectory(prefix="orca dashboard skill CLI ") as temporary_directory:
    temporary_root = Path(temporary_directory) / "harness"
    copied_dashboard = temporary_root / "bin" / "orca-dashboard"
    copied_dashboard.parent.mkdir(parents=True)
    shutil.copy2(DASHBOARD_PATH, copied_dashboard)
    readable_skill = temporary_root / "skills" / "private-readable" / "SKILL.md"
    unreadable_skill = temporary_root / "skills" / "private-unreadable" / "SKILL.md"
    readable_skill.parent.mkdir(parents=True)
    unreadable_skill.parent.mkdir(parents=True)
    readable_skill.write_text("# Skill\n\n## Step 0\n", encoding="utf-8")
    unreadable_skill.write_text("# Unreadable\n\n## Step 1\n", encoding="utf-8")
    unreadable_skill.chmod(0o000)
    skill_failure_env = fixture_environment(temporary_directory)
    try:
        skill_failure_process = subprocess.run(
            [sys.executable, str(copied_dashboard), "snapshot"],
            cwd=temporary_root,
            env=skill_failure_env,
            capture_output=True,
            text=True,
            timeout=10,
        )
    finally:
        unreadable_skill.chmod(0o600)
    skill_failure_payload = parse_stdout_json(skill_failure_process)
    check(
        "snapshot 은 SKILL.md 읽기 실패에도 성공 JSON 과 warning 출력",
        skill_failure_process.returncode == 0
        and isinstance(skill_failure_payload, dict)
        and skill_failure_payload.get("error") is None
        and len(skill_failure_payload.get("warnings", [])) == 1
        and skill_failure_payload["warnings"][0].startswith(
            f"SKILL.md 읽기 실패 {unreadable_skill}: "
        ),
        "exit={} stdout={!r} stderr={!r}".format(
            skill_failure_process.returncode,
            skill_failure_process.stdout[-500:],
            skill_failure_process.stderr[-500:],
        ),
    )

unexpected_env = os.environ.copy()
unexpected_env["ORCA_CLI_COMMAND"] = '"unterminated'
unexpected_process = subprocess.run(
    [sys.executable, str(DASHBOARD_PATH), "snapshot"],
    cwd=ROOT,
    env=unexpected_env,
    capture_output=True,
    text=True,
    timeout=10,
)
unexpected_payload = parse_stdout_json(unexpected_process)
check(
    "snapshot 은 예상 못 한 예외도 exit 1 실패 JSON 으로 변환",
    unexpected_process.returncode == 1
    and isinstance(unexpected_payload, dict)
    and str(unexpected_payload.get("error", "")).startswith("ValueError: ")
    and unexpected_payload.get("warnings") == [],
    "exit={} stdout={!r} stderr={!r}".format(
        unexpected_process.returncode,
        unexpected_process.stdout[-500:],
        unexpected_process.stderr[-500:],
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
check(
    "전체 수집 실패 snapshot 은 빈 warnings 배열 포함",
    isinstance(failure_payload, dict) and failure_payload.get("warnings") == [],
    f"payload={failure_payload!r}",
)

with tempfile.TemporaryDirectory(prefix="orca dashboard partial read ") as temporary_directory:
    partial_failure_env = fixture_environment(temporary_directory)
    partial_failure_env["ORCA_STUB_READ_FAIL"] = "permission denied"
    partial_failure_process = subprocess.run(
        [sys.executable, str(DASHBOARD_PATH), "snapshot"],
        cwd=ROOT,
        env=partial_failure_env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    partial_failure_payload = parse_stdout_json(partial_failure_process)
    check(
        "terminal read 만 실패한 snapshot 은 exit 0 + warning + stale 세션",
        partial_failure_process.returncode == 0
        and isinstance(partial_failure_payload, dict)
        and bool(partial_failure_payload.get("warnings"))
        and len(partial_failure_payload.get("sessions", [])) == 1
        and partial_failure_payload["sessions"][0].get("status") == "stale",
        "exit={} payload={!r} stderr={!r}".format(
            partial_failure_process.returncode,
            partial_failure_payload,
            partial_failure_process.stderr[-500:],
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


def stop_process(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def wait_for_snapshot(process, port, predicate, timeout):
    deadline = time.monotonic() + timeout
    last_detail = "server did not become ready"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stderr = process.stderr.read() if process.stderr else ""
            return None, f"server exited {process.returncode}: {stderr[-800:]}"
        try:
            status, _, body = http_response(f"http://127.0.0.1:{port}/api/snapshot")
            payload = json.loads(body)
            last_detail = f"status={status}, payload={payload!r}"
            if status == 200 and predicate(payload):
                return payload, ""
        except (OSError, TimeoutError, json.JSONDecodeError) as error:
            last_detail = f"{type(error).__name__}: {error}"
        time.sleep(0.03)
    return None, last_detail


def has_checklist_ui_contract(html):
    dark_marker = "@media (prefers-color-scheme: dark)"
    if dark_marker not in html:
        return False
    light_css, dark_css = html.split(dark_marker, 1)
    for state in ("done", "current", "pending"):
        token_pattern = re.compile(
            rf"--[a-z0-9-]*{state}[a-z0-9-]*\s*:", re.IGNORECASE
        )
        if not token_pattern.search(light_css) or not token_pattern.search(dark_css):
            return False
    return (
        "checklist" in html.lower()
        and all(label in html for label in ("완료", "진행 중", "남음", "Step "))
        and all(symbol in html for symbol in ("✔", "▶", "○"))
        and "textContent" in html
    )


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
        check(
            "/ HTML 은 checklist 렌더 코드와 state 별 라이트·다크 토큰 포함",
            root_status == 200 and has_checklist_ui_contract(root_body),
            f"status={root_status}, checklist UI contract missing",
        )
        check("알 수 없는 HTTP 경로는 404", responses["missing"][0] == 404)

print("serve 첫 수집 실행 실패")
with tempfile.TemporaryDirectory(prefix="orca dashboard serve permission ") as temporary_directory:
    non_executable = Path(temporary_directory) / "orca-no-execute"
    non_executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    non_executable.chmod(0o600)
    permission_env = os.environ.copy()
    permission_env["ORCA_CLI_COMMAND"] = shlex.join([str(non_executable)])
    permission_env["ORCA_DASHBOARD_HISTORY_DIR"] = str(
        Path(temporary_directory) / "history"
    )
    permission_port = unused_local_port()
    permission_process = subprocess.Popen(
        [
            sys.executable,
            str(DASHBOARD_PATH),
            "serve",
            "--port",
            str(permission_port),
            "--interval",
            "0.2",
        ],
        cwd=ROOT,
        env=permission_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        permission_payload, permission_error = wait_for_snapshot(
            permission_process,
            permission_port,
            lambda payload: bool(payload.get("error")),
            timeout=5,
        )
    finally:
        stop_process(permission_process)
    check(
        "serve 는 첫 PermissionError 수집 실패에도 기동해 error 노출",
        isinstance(permission_payload, dict) and bool(permission_payload.get("error")),
        permission_error,
    )

print("serve 성공 → 실패 → 성공 복구")
with tempfile.TemporaryDirectory(prefix="orca dashboard serve recovery ") as temporary_directory:
    recovery_env = fixture_environment(temporary_directory)
    recovery_env["ORCA_STUB_CYCLE_FILE"] = str(
        Path(temporary_directory) / "collection-cycle.txt"
    )
    recovery_port = unused_local_port()
    recovery_process = subprocess.Popen(
        [
            sys.executable,
            str(DASHBOARD_PATH),
            "serve",
            "--port",
            str(recovery_port),
            "--interval",
            "0.4",
        ],
        cwd=ROOT,
        env=recovery_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    first_success = None
    failed_cycle = None
    recovered_cycle = None
    recovery_detail = "success/failure/recovery cycle not observed"
    try:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if recovery_process.poll() is not None:
                stderr = recovery_process.stderr.read() if recovery_process.stderr else ""
                recovery_detail = (
                    f"server exited {recovery_process.returncode}: {stderr[-800:]}"
                )
                break
            try:
                status, _, body = http_response(
                    f"http://127.0.0.1:{recovery_port}/api/snapshot"
                )
                payload = json.loads(body)
                recovery_detail = f"status={status}, payload={payload!r}"
                if first_success is None and payload.get("error") is None and payload.get("sessions"):
                    first_success = payload
                elif first_success is not None and failed_cycle is None and payload.get("error"):
                    failed_cycle = payload
                elif failed_cycle is not None and payload.get("error") is None and payload.get("sessions"):
                    recovered_cycle = payload
                    break
            except (OSError, TimeoutError, json.JSONDecodeError):
                pass
            time.sleep(0.03)
    finally:
        stop_process(recovery_process)

    expected_session_ids = (
        [session["id"] for session in first_success["sessions"]]
        if first_success is not None
        else None
    )
    check(
        "serve 는 실패 주기에 직전 sessions 유지 후 다음 성공에서 error 복구",
        first_success is not None
        and failed_cycle is not None
        and recovered_cycle is not None
        and [session["id"] for session in failed_cycle.get("sessions", [])]
        == expected_session_ids
        and [session["id"] for session in recovered_cycle.get("sessions", [])]
        == expected_session_ids,
        recovery_detail,
    )


print("transcript_dir")
expect_equal(
    "Claude projects 경로는 cwd 비영숫자를 하이픈으로 인코딩",
    lambda: dashboard.transcript_dir(
        "/tmp/claude-projects", "/Users/biuea/.harness"
    ),
    "/tmp/claude-projects/-Users-biuea--harness",
)
expect_equal(
    "경로의 공백·대괄호도 문자별 하이픈으로 인코딩",
    lambda: dashboard.transcript_dir(
        "/tmp/claude-projects", "/tmp/project name[1]"
    ),
    "/tmp/claude-projects/-tmp-project-name-1-",
)


def transcript_record(record_type, timestamp, content):
    return json.dumps(
        {
            "type": record_type,
            "timestamp": timestamp,
            "message": {"content": content},
        },
        ensure_ascii=False,
    )


def write_transcript(path, prompt, timestamp="2026-10-07T09:00:00.000Z"):
    path.write_text(
        transcript_record("user", timestamp, prompt) + "\n",
        encoding="utf-8",
    )


def transcript_read_error_observation(action):
    error_type = getattr(dashboard, "TranscriptReadError", None)
    class_contract = (
        isinstance(error_type, type) and issubclass(error_type, OSError)
    )
    try:
        action()
    except Exception as error:
        return {
            "classContract": class_contract,
            "raised": True,
            "isExpected": class_contract and isinstance(error, error_type),
            "actualType": type(error).__name__,
            "message": str(error),
        }
    return {
        "classContract": class_contract,
        "raised": False,
        "isExpected": False,
        "actualType": None,
        "message": "",
    }


def transcript_error_matches(observation, failed_path):
    message = observation.get("message", "")
    cause_text = message.replace(str(failed_path), "").strip()
    return (
        observation.get("classContract") is True
        and observation.get("raised") is True
        and observation.get("isExpected") is True
        and str(failed_path) in message
        and bool(cause_text)
    )


def denied_directory_observation():
    with tempfile.TemporaryDirectory(
        prefix="orca-dashboard-r30-permission-", dir="/tmp"
    ) as temporary_directory:
        temporary_root = Path(temporary_directory)
        temporary_root.chmod(0o755)
        dashboard_copy = temporary_root / "orca-dashboard.py"
        shutil.copy2(DASHBOARD_PATH, dashboard_copy)
        denied_directory = temporary_root / "denied-transcripts"
        denied_directory.mkdir()
        write_transcript(denied_directory / "denied.jsonl", "권한 거부 요청")
        denied_directory.chmod(0o000)
        observation = None
        permissions_restored = False
        try:
            if os.geteuid() != 0:
                observation = transcript_read_error_observation(
                    lambda: dashboard.find_transcript(
                        str(denied_directory), "권한 거부 요청"
                    )
                )
            else:
                import pwd

                nobody = pwd.getpwnam("nobody")

                def demote_to_nobody():
                    os.setgroups([])
                    os.setgid(nobody.pw_gid)
                    os.setuid(nobody.pw_uid)

                probe = r'''
import importlib.machinery
import importlib.util
import json
import sys

sys.dont_write_bytecode = True
loader = importlib.machinery.SourceFileLoader("orca_dashboard_permission_probe", sys.argv[1])
spec = importlib.util.spec_from_loader("orca_dashboard_permission_probe", loader)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
error_type = getattr(module, "TranscriptReadError", None)
class_contract = isinstance(error_type, type) and issubclass(error_type, OSError)
try:
    module.find_transcript(sys.argv[2], "권한 거부 요청")
except Exception as error:
    payload = {
        "classContract": class_contract,
        "raised": True,
        "isExpected": class_contract and isinstance(error, error_type),
        "actualType": type(error).__name__,
        "message": str(error),
    }
else:
    payload = {
        "classContract": class_contract,
        "raised": False,
        "isExpected": False,
        "actualType": None,
        "message": "",
    }
print(json.dumps(payload, ensure_ascii=False))
'''
                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        probe,
                        str(dashboard_copy),
                        str(denied_directory),
                    ],
                    cwd="/tmp",
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                    preexec_fn=demote_to_nobody,
                )
                try:
                    observation = json.loads(result.stdout)
                except json.JSONDecodeError:
                    observation = {
                        "classContract": False,
                        "raised": False,
                        "isExpected": False,
                        "actualType": "permission probe failure",
                        "message": (
                            f"exit={result.returncode}, stdout={result.stdout!r}, "
                            f"stderr={result.stderr!r}"
                        ),
                    }
        finally:
            denied_directory.chmod(0o700)
            permissions_restored = (
                denied_directory.stat().st_mode & 0o777
            ) == 0o700
        observation["permissionsRestored"] = permissions_restored
        observation["failedPath"] = str(denied_directory)
        return observation


print("find_transcript")
with tempfile.TemporaryDirectory(prefix="orca dashboard transcripts ") as temporary_directory:
    transcript_directory = Path(temporary_directory)
    matching_transcript = transcript_directory / "matching.jsonl"
    matching_transcript.write_text(
        transcript_record(
            "user", "2026-10-07T08:59:00.000Z", "이전 사용자 요청"
        )
        + "\n"
        + transcript_record(
            "user",
            "2026-10-07T09:00:00.000Z",
            "세션   상세\n페이지를 구현해 주세요",
        )
        + "\n",
        encoding="utf-8",
    )
    expect_equal(
        "마지막 사용자 요청과 공백 정규화 후 일치하는 transcript 1개 선택",
        lambda: dashboard.find_transcript(
            str(transcript_directory), "세션 상세 페이지를 구현해 주세요"
        ),
        str(matching_transcript),
    )

with tempfile.TemporaryDirectory(prefix="orca dashboard latest transcript ") as temporary_directory:
    transcript_directory = Path(temporary_directory)
    older_transcript = transcript_directory / "older.jsonl"
    newer_transcript = transcript_directory / "newer.jsonl"
    write_transcript(older_transcript, "동일한 요청")
    write_transcript(newer_transcript, "동일한 요청")
    os.utime(older_transcript, (100, 100))
    os.utime(newer_transcript, (200, 200))
    expect_equal(
        "일치 transcript 2개면 mtime 최신 파일 선택",
        lambda: dashboard.find_transcript(
            str(transcript_directory), "동일한 요청"
        ),
        str(newer_transcript),
    )
    expect_equal(
        "사용자 요청이 불일치하면 transcript 없음",
        lambda: dashboard.find_transcript(
            str(transcript_directory), "다른 요청"
        ),
        None,
    )
    expect_equal(
        "prompt None 이면 transcript 없음",
        lambda: dashboard.find_transcript(str(transcript_directory), None),
        None,
    )

expect_equal(
    "transcript 디렉토리가 없으면 None",
    lambda: dashboard.find_transcript(
        "/definitely/missing/orca-dashboard-transcripts", "요청"
    ),
    None,
)

with tempfile.TemporaryDirectory(prefix="orca dashboard broken transcript ") as temporary_directory:
    transcript_directory = Path(temporary_directory)
    broken_transcript = transcript_directory / "broken.jsonl"
    broken_transcript.mkdir()
    valid_transcript = transcript_directory / "valid.jsonl"
    write_transcript(valid_transcript, "깨진 파일을 건너뛰는 요청")
    expect_equal(
        "읽기 실패 transcript 는 건너뛰고 일치 파일 선택",
        lambda: dashboard.find_transcript(
            str(transcript_directory), "깨진 파일을 건너뛰는 요청"
        ),
        str(valid_transcript),
    )

with tempfile.TemporaryDirectory(prefix="orca dashboard assistant fallback ") as temporary_directory:
    transcript_directory = Path(temporary_directory)
    fallback_transcript = transcript_directory / "assistant-match.jsonl"
    fallback_transcript.write_text(
        transcript_record(
            "user", "2026-10-07T09:00:00.000Z", "prompt 와 다른 사용자 요청"
        )
        + "\n"
        + transcript_record(
            "assistant",
            "2026-10-07T09:00:01.000Z",
            [{"type": "text", "text": "마지막 assistant 응답으로 찾습니다"}],
        )
        + "\n",
        encoding="utf-8",
    )
    expect_equal(
        "prompt 불일치 시 마지막 assistant 텍스트와 last_message 일치 파일 선택",
        lambda: dashboard.find_transcript(
            str(transcript_directory),
            "덮어쓴 prompt",
            "마지막 assistant 응답으로 찾습니다",
        ),
        str(fallback_transcript),
    )
    expect_equal(
        "prompt None 이어도 마지막 assistant 텍스트와 last_message 일치 파일 선택",
        lambda: dashboard.find_transcript(
            str(transcript_directory),
            None,
            "마지막 assistant 응답으로 찾습니다",
        ),
        str(fallback_transcript),
    )
    expect_equal(
        "prompt 와 last_message 가 모두 불일치하면 transcript 없음",
        lambda: dashboard.find_transcript(
            str(transcript_directory), "불일치 prompt", "불일치 assistant 응답"
        ),
        None,
    )
    expect_equal(
        "prompt 와 last_message 가 모두 None 이면 transcript 없음",
        lambda: dashboard.find_transcript(str(transcript_directory), None, None),
        None,
    )

with tempfile.TemporaryDirectory(prefix="orca dashboard prompt priority ") as temporary_directory:
    transcript_directory = Path(temporary_directory)
    prompt_match = transcript_directory / "older-prompt-match.jsonl"
    assistant_match = transcript_directory / "newer-assistant-match.jsonl"
    prompt_match.write_text(
        transcript_record("user", "2026-10-07T09:00:00.000Z", "원래 사용자 요청")
        + "\n"
        + transcript_record(
            "assistant",
            "2026-10-07T09:00:01.000Z",
            [{"type": "text", "text": "다른 assistant 응답"}],
        )
        + "\n",
        encoding="utf-8",
    )
    assistant_match.write_text(
        transcript_record("user", "2026-10-07T09:00:02.000Z", "다른 사용자 요청")
        + "\n"
        + transcript_record(
            "assistant",
            "2026-10-07T09:00:03.000Z",
            [{"type": "text", "text": "같은 마지막 assistant 응답"}],
        )
        + "\n",
        encoding="utf-8",
    )
    os.utime(prompt_match, (100, 100))
    os.utime(assistant_match, (200, 200))
    expect_equal(
        "더 최신 last_message 일치 파일보다 prompt 일치 파일 우선",
        lambda: dashboard.find_transcript(
            str(transcript_directory),
            "원래 사용자 요청",
            "같은 마지막 assistant 응답",
        ),
        str(prompt_match),
    )

with tempfile.TemporaryDirectory(prefix="orca dashboard last assistant only ") as temporary_directory:
    transcript_directory = Path(temporary_directory)
    previous_only = transcript_directory / "previous-assistant-match.jsonl"
    previous_only.write_text(
        transcript_record("user", "2026-10-07T09:00:00.000Z", "다른 사용자 요청")
        + "\n"
        + transcript_record(
            "assistant",
            "2026-10-07T09:00:01.000Z",
            [{"type": "text", "text": "이전 assistant 응답만 일치"}],
        )
        + "\n"
        + transcript_record(
            "assistant",
            "2026-10-07T09:00:02.000Z",
            [{"type": "text", "text": "실제 마지막 assistant 응답"}],
        )
        + "\n",
        encoding="utf-8",
    )
    expect_equal(
        "이전 assistant 텍스트만 일치하면 transcript 없음",
        lambda: dashboard.find_transcript(
            str(transcript_directory), "불일치 prompt", "이전 assistant 응답만 일치"
        ),
        None,
    )

with tempfile.TemporaryDirectory(prefix="orca dashboard continuation transcript ") as temporary_directory:
    transcript_directory = Path(temporary_directory)
    continued_transcript = transcript_directory / "continued.jsonl"
    continued_transcript.write_text(
        transcript_record("user", "2026-10-07T09:00:00.000Z", "압축 전 실제 마지막 요청")
        + "\n"
        + transcript_record(
            "user",
            "2026-10-07T09:00:01.000Z",
            "This session is being continued from a previous conversation that ran out of context.",
        )
        + "\n",
        encoding="utf-8",
    )
    expect_equal(
        "continuation 요약이 마지막이어도 그 이전 실제 사용자 요청으로 선택",
        lambda: dashboard.find_transcript(
            str(transcript_directory), "압축 전 실제 마지막 요청"
        ),
        str(continued_transcript),
    )


def r25_prompt_match(transcript_text, orca_text):
    with tempfile.TemporaryDirectory(prefix="orca dashboard r25 prompt ") as temporary_directory:
        transcript_path = Path(temporary_directory) / "prompt.jsonl"
        write_transcript(transcript_path, transcript_text)
        return dashboard.find_transcript(temporary_directory, orca_text) == str(
            transcript_path
        )


def r25_assistant_match(transcript_text, orca_text):
    with tempfile.TemporaryDirectory(prefix="orca dashboard r25 assistant ") as temporary_directory:
        transcript_path = Path(temporary_directory) / "assistant.jsonl"
        transcript_path.write_text(
            transcript_record(
                "user", "2026-10-07T09:00:00.000Z", "일치하지 않는 사용자 요청"
            )
            + "\n"
            + transcript_record(
                "assistant",
                "2026-10-07T09:00:01.000Z",
                [{"type": "text", "text": transcript_text}],
            )
            + "\n",
            encoding="utf-8",
        )
        return dashboard.find_transcript(
            temporary_directory, "일치하지 않는 Orca prompt", orca_text
        ) == str(transcript_path)


print("find_transcript 전체 일치와 잘린 Orca 텍스트")
R25_PREFIX_60 = "가" * 60
R25_PREFIX_59 = "나" * 59
for match_source, match_fixture in (
    ("① 사용자 요청", r25_prompt_match),
    ("② assistant 응답", r25_assistant_match),
):
    expect_equal(
        f"{match_source}은 앞 60자가 같아도 뒷부분이 다르면 불일치",
        lambda match_fixture=match_fixture: match_fixture(
            R25_PREFIX_60 + " transcript 뒷부분",
            R25_PREFIX_60 + " Orca 뒷부분",
        ),
        False,
    )
    expect_equal(
        f"{match_source}은 공백 정규화 후 전체가 같으면 일치",
        lambda match_fixture=match_fixture: match_fixture(
            R25_PREFIX_60 + "   같은\n전체 텍스트",
            R25_PREFIX_60 + " 같은 전체 텍스트",
        ),
        True,
    )
    expect_equal(
        (
            "① 사용자 요청은 prompt 원문이 200자 미만이면 "
            "60자 이상 접두사만 일치해도 불일치"
            if match_source == "① 사용자 요청"
            else "② assistant 응답은 60자 이상 접두사만 일치해도 불일치"
        ),
        lambda match_fixture=match_fixture: match_fixture(
            R25_PREFIX_60 + " transcript 에만 남은 뒷부분",
            R25_PREFIX_60,
        ),
        False,
    )
    expect_equal(
        f"{match_source}은 Orca 쪽 잘린 접두사가 60자 미만이면 불일치",
        lambda match_fixture=match_fixture: match_fixture(
            R25_PREFIX_59 + " transcript 에만 남은 뒷부분",
            R25_PREFIX_59,
        ),
        False,
    )

expect_equal(
    "ORCA_PROMPT_LIMIT = 200",
    lambda: dashboard.ORCA_PROMPT_LIMIT,
    200,
)

with tempfile.TemporaryDirectory(prefix="orca dashboard r29 exact priority ") as temporary_directory:
    transcript_directory = Path(temporary_directory)
    exact_prompt = "단일 완전한 요청 " + ("가" * 80)
    exact_older = transcript_directory / "older-exact.jsonl"
    prefixed_newer = transcript_directory / "newer-extended.jsonl"
    write_transcript(exact_older, exact_prompt)
    write_transcript(prefixed_newer, exact_prompt + " 추가 조건")
    os.utime(exact_older, (100, 100))
    os.utime(prefixed_newer, (200, 200))
    expect_equal(
        "정확한 S 이전 파일과 S+추가 최신 파일이 공존하면 정확한 이전 파일 선택",
        lambda: dashboard.find_transcript(
            str(transcript_directory), exact_prompt
        ),
        str(exact_older),
    )

R29_TRUNCATED_PROMPT = "다" * 200
expect_equal(
    "prompt 원문 200자와 더 긴 transcript 요청의 접두사가 일치하면 일치",
    lambda: r25_prompt_match(
        R29_TRUNCATED_PROMPT + " transcript 에만 남은 추가 요청",
        R29_TRUNCATED_PROMPT,
    ),
    True,
)

print("find_transcript 읽기 실패 노출")
transcript_error_type = getattr(dashboard, "TranscriptReadError", None)
check(
    "TranscriptReadError 는 OSError 하위 클래스",
    isinstance(transcript_error_type, type)
    and issubclass(transcript_error_type, OSError),
    f"actual={transcript_error_type!r}",
)

with tempfile.TemporaryDirectory(prefix="orca dashboard r30 all unreadable ") as temporary_directory:
    transcript_directory = Path(temporary_directory)
    failed_candidate = transcript_directory / "all-unreadable.jsonl"
    failed_candidate.mkdir()
    all_unreadable = transcript_read_error_observation(
        lambda: dashboard.find_transcript(
            str(transcript_directory), "일치하지 않는 요청"
        )
    )
    check(
        "후보 전부 읽기 실패 + 일치 없음은 경로·원인을 담은 TranscriptReadError",
        transcript_error_matches(all_unreadable, failed_candidate),
        f"observation={all_unreadable!r}",
    )

permission_observation = denied_directory_observation()
check(
    "transcript 디렉토리 권한 거부는 권한 복구 후 TranscriptReadError",
    permission_observation.get("permissionsRestored") is True
    and transcript_error_matches(
        permission_observation, permission_observation.get("failedPath")
    ),
    f"observation={permission_observation!r}",
)


from datetime import datetime


def utc_ms(timestamp):
    return int(datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp() * 1000)


def notification(tool_use_id, status, summary):
    return (
        "<task-notification>\n"
        f"<tool-use-id>{tool_use_id}</tool-use-id>\n"
        f"<status>{status}</status>\n"
        f"<summary>{summary}</summary>\n"
        "</task-notification>"
    )


TRANSCRIPT_TIMESTAMPS = [
    f"2026-10-07T09:00:{second:02d}.000Z" for second in range(24)
]
TRANSCRIPT_LINES = [
    transcript_record("user", TRANSCRIPT_TIMESTAMPS[0], "첫 요청\n세부 설명"),
    transcript_record(
        "user",
        TRANSCRIPT_TIMESTAMPS[1],
        notification("toolu_untracked", "completed", "알림은 prompt 가 아님"),
    ),
    transcript_record(
        "user",
        TRANSCRIPT_TIMESTAMPS[2],
        [{"type": "text", "text": "  둘째 요청"}],
    ),
    transcript_record(
        "assistant",
        TRANSCRIPT_TIMESTAMPS[3],
        [
            {
                "type": "tool_use",
                "id": "toolu_agent_running",
                "name": "Agent",
                "input": {
                    "description": "실행 중 서브에이전트",
                    "subagent_type": "Explore",
                    "model": "opus",
                    "prompt": "계약을 조사한다",
                    "run_in_background": True,
                },
            }
        ],
    ),
    transcript_record(
        "assistant",
        TRANSCRIPT_TIMESTAMPS[4],
        [
            {
                "type": "tool_use",
                "id": "toolu_agent_done",
                "name": "Task",
                "input": {
                    "description": "완료된 서브에이전트",
                    "subagent_type": "general-purpose",
                    "model": "sonnet",
                    "prompt": "테스트를 작성한다",
                    "run_in_background": True,
                },
            }
        ],
    ),
    transcript_record(
        "user",
        TRANSCRIPT_TIMESTAMPS[5],
        [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_agent_done",
                "content": "Async agent launched",
            }
        ],
    ),
    transcript_record(
        "assistant",
        TRANSCRIPT_TIMESTAMPS[6],
        [
            {
                "type": "tool_use",
                "id": "toolu_shell_ok",
                "name": "Bash",
                "input": {
                    "command": "python3 tests/test_orca_dashboard.py",
                    "description": "성공 셸",
                    "run_in_background": True,
                },
            }
        ],
    ),
    transcript_record(
        "assistant",
        TRANSCRIPT_TIMESTAMPS[7],
        [
            {
                "type": "tool_use",
                "id": "toolu_shell_failed",
                "name": "Bash",
                "input": {
                    "command": "false",
                    "description": "실패 셸",
                    "run_in_background": True,
                },
            }
        ],
    ),
    transcript_record(
        "assistant",
        TRANSCRIPT_TIMESTAMPS[8],
        [
            {
                "type": "tool_use",
                "id": "toolu_shell_killed",
                "name": "Bash",
                "input": {
                    "command": "sleep 10",
                    "run_in_background": True,
                },
            }
        ],
    ),
    "{broken json line",
    transcript_record(
        "user",
        TRANSCRIPT_TIMESTAMPS[10],
        notification(
            "toolu_agent_done", "completed", "서브에이전트 작업 완료"
        ),
    ),
    transcript_record(
        "user",
        TRANSCRIPT_TIMESTAMPS[11],
        [
            {
                "type": "text",
                "text": notification(
                    "toolu_shell_ok",
                    "completed",
                    'Background command "tests" completed (exit code 0)',
                ),
            }
        ],
    ),
    transcript_record(
        "user",
        TRANSCRIPT_TIMESTAMPS[12],
        notification(
            "toolu_shell_failed",
            "completed",
            'Background command "false" completed (exit code 2)',
        ),
    ),
    transcript_record(
        "user",
        TRANSCRIPT_TIMESTAMPS[13],
        notification("toolu_shell_killed", "killed", "사용자가 작업을 중단함"),
    ),
    transcript_record(
        "assistant",
        TRANSCRIPT_TIMESTAMPS[14],
        [
            {
                "type": "tool_use",
                "id": "toolu_foreground_done",
                "name": "Agent",
                "input": {
                    "description": "포그라운드 완료",
                    "subagent_type": "Explore",
                    "prompt": "확인한다",
                },
            }
        ],
    ),
    transcript_record(
        "user",
        TRANSCRIPT_TIMESTAMPS[15],
        [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_foreground_done",
                "content": "결과",
            }
        ],
    ),
    transcript_record(
        "assistant",
        TRANSCRIPT_TIMESTAMPS[16],
        [
            {
                "type": "tool_use",
                "id": "toolu_foreground_failed",
                "name": "Task",
                "input": {
                    "description": "포그라운드 실패",
                    "subagent_type": "general-purpose",
                    "prompt": "실패한다",
                    "run_in_background": False,
                },
            }
        ],
    ),
    transcript_record(
        "user",
        TRANSCRIPT_TIMESTAMPS[17],
        [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_foreground_failed",
                "is_error": True,
                "content": "오류",
            }
        ],
    ),
    transcript_record(
        "assistant",
        TRANSCRIPT_TIMESTAMPS[18],
        [
            {
                "type": "tool_use",
                "id": "toolu_foreground_running",
                "name": "Agent",
                "input": {
                    "description": "포그라운드 실행 중",
                    "subagent_type": "Explore",
                    "prompt": "계속 실행한다",
                },
            }
        ],
    ),
    transcript_record(
        "assistant",
        TRANSCRIPT_TIMESTAMPS[19],
        [
            {
                "type": "tool_use",
                "id": "toolu_foreground_bash",
                "name": "Bash",
                "input": {"command": "pwd", "description": "일반 셸"},
            }
        ],
    ),
    transcript_record(
        "assistant",
        TRANSCRIPT_TIMESTAMPS[20],
        [
            {
                "type": "text",
                "text": "현재 Step 4 진행 중입니다. Step 8은 다음 단계입니다.",
            }
        ],
    ),
    transcript_record(
        "assistant",
        TRANSCRIPT_TIMESTAMPS[21],
        [{"type": "text", "text": "Step 4 검증을 계속합니다."}],
    ),
    transcript_record(
        "assistant",
        TRANSCRIPT_TIMESTAMPS[22],
        [
            {
                "type": "text",
                "text": "Step 6 구현 중입니다. 다음은 Step 8입니다.",
            }
        ],
    ),
    transcript_record(
        "assistant",
        TRANSCRIPT_TIMESTAMPS[23],
        [{"type": "text", "text": "진행 상태를 기록합니다."}],
    ),
]


def parsed_transcript():
    return dashboard.parse_transcript(TRANSCRIPT_LINES)


print("parse_transcript")
expect_equal(
    "prompts 는 continuation 압축 요약을 사용자 요청에서 제외",
    lambda: dashboard.parse_transcript(
        [
            transcript_record(
                "user", "2026-10-07T09:00:00.000Z", "압축 전 실제 요청"
            ),
            transcript_record(
                "user",
                "2026-10-07T09:00:01.000Z",
                "This session is being continued from a previous conversation that ran out of context.",
            ),
            transcript_record(
                "user", "2026-10-07T09:00:02.000Z", "압축 후 실제 요청"
            ),
        ]
    )["prompts"],
    [
        {"at": utc_ms("2026-10-07T09:00:00.000Z"), "text": "압축 전 실제 요청"},
        {"at": utc_ms("2026-10-07T09:00:02.000Z"), "text": "압축 후 실제 요청"},
    ],
)
expect_equal(
    "prompt 는 task-notification·tool_result 전용 user 줄을 제외",
    lambda: parsed_transcript()["prompts"],
    [
        {"at": utc_ms(TRANSCRIPT_TIMESTAMPS[0]), "text": "첫 요청"},
        {"at": utc_ms(TRANSCRIPT_TIMESTAMPS[2]), "text": "둘째 요청"},
    ],
)
expect_equal(
    "tasks 는 추적 대상 시작순으로 반환",
    lambda: [task["id"] for task in parsed_transcript()["tasks"]],
    [
        "toolu_agent_running",
        "toolu_agent_done",
        "toolu_shell_ok",
        "toolu_shell_failed",
        "toolu_shell_killed",
        "toolu_foreground_done",
        "toolu_foreground_failed",
        "toolu_foreground_running",
    ],
)
expect_predicate(
    "task 항목은 공개 키 집합을 모두 포함",
    lambda: parsed_transcript()["tasks"],
    lambda tasks: all(
        set(task)
        == {
            "id",
            "kind",
            "title",
            "agentType",
            "model",
            "background",
            "state",
            "startedAt",
            "endedAt",
            "summary",
        }
        for task in tasks
    ),
    "every task has exactly the public task keys",
)
expect_equal(
    "백그라운드 shell 은 제목·시각·종료 요약을 공개 계약대로 반환",
    lambda: {
        task["id"]: task for task in parsed_transcript()["tasks"]
    }["toolu_shell_ok"],
    {
        "id": "toolu_shell_ok",
        "kind": "shell",
        "title": "성공 셸",
        "agentType": None,
        "model": None,
        "background": True,
        "state": "completed",
        "startedAt": utc_ms(TRANSCRIPT_TIMESTAMPS[6]),
        "endedAt": utc_ms(TRANSCRIPT_TIMESTAMPS[11]),
        "summary": 'Background command "tests" completed (exit code 0)',
    },
)
expect_predicate(
    "백그라운드 agent 는 알림 없으면 running, 알림 있으면 completed",
    lambda: {task["id"]: task for task in parsed_transcript()["tasks"]},
    lambda tasks: tasks["toolu_agent_running"]["state"] == "running"
    and tasks["toolu_agent_running"]["endedAt"] is None
    and tasks["toolu_agent_done"]["state"] == "completed"
    and tasks["toolu_agent_done"]["endedAt"]
    == utc_ms(TRANSCRIPT_TIMESTAMPS[10])
    and tasks["toolu_agent_done"]["agentType"] == "general-purpose"
    and tasks["toolu_agent_done"]["model"] == "sonnet"
    and tasks["toolu_agent_done"]["background"] is True,
    "background agent running/completed states and public metadata",
)
expect_predicate(
    "백그라운드 shell exit code 0 은 completed, exit code 2 는 failed",
    lambda: {task["id"]: task for task in parsed_transcript()["tasks"]},
    lambda tasks: tasks["toolu_shell_ok"]["state"] == "completed"
    and tasks["toolu_shell_failed"]["state"] == "failed"
    and tasks["toolu_shell_failed"]["summary"].endswith("(exit code 2)"),
    "exit-code based shell states",
)
expect_predicate(
    "백그라운드 status killed 는 failed",
    lambda: {task["id"]: task for task in parsed_transcript()["tasks"]},
    lambda tasks: tasks["toolu_shell_killed"]["state"] == "failed"
    and tasks["toolu_shell_killed"]["title"] == "sleep 10",
    "killed shell failed with command fallback title",
)
expect_predicate(
    "포그라운드 Agent 는 tool_result 성공·오류·없음에 따라 상태 판정",
    lambda: {task["id"]: task for task in parsed_transcript()["tasks"]},
    lambda tasks: tasks["toolu_foreground_done"]["state"] == "completed"
    and tasks["toolu_foreground_failed"]["state"] == "failed"
    and tasks["toolu_foreground_running"]["state"] == "running"
    and tasks["toolu_foreground_done"]["background"] is False,
    "foreground Agent completed/failed/running states",
)
expect_predicate(
    "run_in_background 없는 Bash 는 tasks 에서 제외",
    lambda: parsed_transcript()["tasks"],
    lambda tasks: "toolu_foreground_bash" not in {task["id"] for task in tasks},
    "foreground Bash id absent",
)
expect_equal(
    "Step 은 예고 문장을 제외하고 값이 바뀐 시점만 기록",
    lambda: parsed_transcript()["steps"],
    [
        {"at": utc_ms(TRANSCRIPT_TIMESTAMPS[20]), "step": 4},
        {"at": utc_ms(TRANSCRIPT_TIMESTAMPS[22]), "step": 6},
    ],
)
expect_equal(
    "깨진 JSON 줄을 건너뛰고 마지막 활동 시각 반환",
    lambda: parsed_transcript()["lastActivityAt"],
    utc_ms(TRANSCRIPT_TIMESTAMPS[23]),
)


DETAIL_SESSION = {
    "id": "session-detail",
    "name": "상세 세션",
    "agentType": "claude",
    "agentState": "working",
    "toolName": "Agent",
    "status": "blocked",
    "reason": "승인이 필요합니다",
    "progress": {"percent": 44, "basis": "/private-roadmap Step 4"},
    "checklist": None,
}
DETAIL_TRANSCRIPT = {
    "prompts": [{"at": 100, "text": "상세 페이지를 구현해 주세요"}],
    "steps": [{"at": 200, "step": 4}],
    "tasks": [
        {
            "id": "running-old",
            "kind": "agent",
            "title": "기존 실행 작업",
            "agentType": "Explore",
            "model": "opus",
            "background": True,
            "state": "running",
            "startedAt": 400,
            "endedAt": None,
            "summary": None,
        },
        {
            "id": "failed",
            "kind": "shell",
            "title": "실패 작업",
            "agentType": None,
            "model": None,
            "background": True,
            "state": "failed",
            "startedAt": 500,
            "endedAt": 700,
            "summary": "exit code 2",
        },
        {
            "id": "completed",
            "kind": "agent",
            "title": "완료 작업",
            "agentType": "general-purpose",
            "model": "sonnet",
            "background": False,
            "state": "completed",
            "startedAt": 600,
            "endedAt": 800,
            "summary": "완료됨",
        },
        {
            "id": "running-new",
            "kind": "shell",
            "title": "최신 실행 작업",
            "agentType": None,
            "model": None,
            "background": True,
            "state": "running",
            "startedAt": 900,
            "endedAt": None,
            "summary": None,
        },
    ],
    "lastActivityAt": 900,
}


def built_detail():
    return dashboard.build_detail(
        DETAIL_SESSION, DETAIL_TRANSCRIPT, now_ms=NOW_MS
    )


print("build_detail")
expect_equal(
    "children 은 running 우선 뒤 최신 시작순 정렬",
    lambda: [child["id"] for child in built_detail()["agents"]["children"]],
    ["running-new", "running-old", "completed", "failed"],
)
expect_equal(
    "agents main 은 세션 공개 필드로 조립",
    lambda: built_detail()["agents"]["main"],
    {
        "name": "상세 세션",
        "agentType": "claude",
        "state": "working",
        "toolName": "Agent",
    },
)
expect_equal(
    "agents main state 는 agentState working 보다 mainState done 을 우선",
    lambda: dashboard.build_detail(
        {**DETAIL_SESSION, "agentState": "working", "mainState": "done"},
        DETAIL_TRANSCRIPT,
        now_ms=NOW_MS,
    )["agents"]["main"]["state"],
    "done",
)
expect_equal(
    "agents mainState 가 None 이면 agentState 로 대체",
    lambda: dashboard.build_detail(
        {**DETAIL_SESSION, "agentState": "working", "mainState": None},
        DETAIL_TRANSCRIPT,
        now_ms=NOW_MS,
    )["agents"]["main"]["state"],
    "working",
)
expect_equal(
    "timeline 은 kind·문구를 시간순으로 조립",
    lambda: built_detail()["timeline"],
    [
        {"at": 100, "kind": "prompt", "text": "상세 페이지를 구현해 주세요"},
        {"at": 200, "kind": "step", "text": "Step 4 진입"},
        {"at": 400, "kind": "task_start", "text": "기존 실행 작업 시작"},
        {"at": 500, "kind": "task_start", "text": "실패 작업 시작"},
        {"at": 600, "kind": "task_start", "text": "완료 작업 시작"},
        {"at": 700, "kind": "task_end", "text": "실패 작업 실패"},
        {"at": 800, "kind": "task_end", "text": "완료 작업 완료"},
        {"at": 900, "kind": "task_start", "text": "최신 실행 작업 시작"},
    ],
)
expect_equal(
    "blockers 는 session blocked 와 failed task 를 함께 노출",
    lambda: built_detail()["blockers"],
    [
        {"source": "session", "text": "승인이 필요합니다"},
        {"source": "task", "text": "실패 작업 실패: exit code 2"},
    ],
)

timeline_limit_transcript = {
    "prompts": [
        {"at": number, "text": f"요청 {number}"} for number in range(31)
    ],
    "steps": [
        {"at": 100 + number, "step": number} for number in range(30)
    ],
    "tasks": [],
    "lastActivityAt": 129,
}
expect_predicate(
    "timeline 은 시간순 최근 60개만 유지",
    lambda: dashboard.build_detail(
        DETAIL_SESSION, timeline_limit_transcript, now_ms=NOW_MS
    )["timeline"],
    lambda timeline: len(timeline) == 60
    and timeline[0] == {"at": 1, "kind": "prompt", "text": "요청 1"}
    and timeline[-1] == {"at": 129, "kind": "step", "text": "Step 29 진입"},
    "60 chronological events with the oldest event dropped",
)
expect_equal(
    "transcript None 이면 children·timeline 은 비고 transcript false",
    lambda: {
        "children": detail["agents"]["children"],
        "timeline": detail["timeline"],
        "blockers": detail["blockers"],
        "transcript": detail["transcript"],
    }
    if (
        detail := dashboard.build_detail(
            DETAIL_SESSION, None, now_ms=NOW_MS
        )
    )
    else None,
    {
        "children": [],
        "timeline": [],
        "blockers": [{"source": "session", "text": "승인이 필요합니다"}],
        "transcript": False,
    },
)


def has_detail_state_tokens(html):
    dark_marker = "@media (prefers-color-scheme: dark)"
    if dark_marker not in html:
        return False
    light_css, dark_css = html.split(dark_marker, 1)
    for state in ("running", "completed", "failed"):
        token_pattern = re.compile(
            rf"--[a-z0-9-]*{state}[a-z0-9-]*\s*:", re.IGNORECASE
        )
        if not token_pattern.search(light_css) or not token_pattern.search(dark_css):
            return False
    return True


def avoids_data_inner_html(html):
    assignments = re.findall(r"\.innerHTML\s*=\s*([^;\n]+)", html)
    return all(value.strip() in ('""', "''", "``") for value in assignments)


print("serve session detail · detail UI")
with tempfile.TemporaryDirectory(prefix="orca dashboard detail serve ") as temporary_directory:
    detail_env = fixture_environment(temporary_directory)
    detail_env["CLAUDE_PROJECTS_DIR"] = str(
        Path(temporary_directory) / "claude-projects"
    )
    Path(detail_env["CLAUDE_PROJECTS_DIR"]).mkdir()
    detail_port = unused_local_port()
    detail_process = subprocess.Popen(
        [
            sys.executable,
            str(DASHBOARD_PATH),
            "serve",
            "--port",
            str(detail_port),
            "--interval",
            "0.1",
        ],
        cwd=ROOT,
        env=detail_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    detail_ready = None
    detail_ready_error = "server did not become ready"
    existing_detail_response = None
    missing_detail_response = None
    detail_root_response = None
    try:
        detail_ready, detail_ready_error = wait_for_snapshot(
            detail_process,
            detail_port,
            lambda payload: any(
                session.get("id") == "tab-stub:leaf-stub"
                for session in payload.get("sessions", [])
            ),
            timeout=5,
        )
        if detail_ready is not None:
            existing_detail_response = http_response(
                f"http://127.0.0.1:{detail_port}/api/session?id=tab-stub:leaf-stub"
            )
            missing_detail_response = http_response(
                f"http://127.0.0.1:{detail_port}/api/session?id=missing-session"
            )
            detail_root_response = http_response(
                f"http://127.0.0.1:{detail_port}/"
            )
    finally:
        stop_process(detail_process)

    existing_detail_payload = None
    missing_detail_payload = None
    if existing_detail_response is not None:
        try:
            existing_detail_payload = json.loads(existing_detail_response[2])
        except json.JSONDecodeError:
            pass
    if missing_detail_response is not None:
        try:
            missing_detail_payload = json.loads(missing_detail_response[2])
        except json.JSONDecodeError:
            pass

    check(
        "/api/session 기존 id 는 200 JSON 과 상세 키 집합 반환",
        existing_detail_response is not None
        and existing_detail_response[0] == 200
        and existing_detail_response[1].get_content_type() == "application/json"
        and isinstance(existing_detail_payload, dict)
        and set(existing_detail_payload)
        >= {
            "session",
            "agents",
            "timeline",
            "blockers",
            "transcript",
        }
        and existing_detail_payload.get("transcript") is False,
        detail_ready_error
        if detail_ready is None
        else f"response={existing_detail_response!r}, payload={existing_detail_payload!r}",
    )
    check(
        "/api/session 없는 id 는 404 error JSON",
        missing_detail_response is not None
        and missing_detail_response[0] == 404
        and missing_detail_response[1].get_content_type() == "application/json"
        and isinstance(missing_detail_payload, dict)
        and set(missing_detail_payload) == {"error"}
        and bool(missing_detail_payload["error"]),
        detail_ready_error
        if detail_ready is None
        else f"response={missing_detail_response!r}, payload={missing_detail_payload!r}",
    )

    detail_html = detail_root_response[2] if detail_root_response is not None else ""
    check(
        "/ HTML 은 api/session 호출과 hash 라우팅 포함",
        "/api/session" in detail_html
        and ("hashchange" in detail_html or "location.hash" in detail_html),
        "detail API or hash route missing",
    )
    check(
        "/ HTML 은 running·completed·failed 라이트·다크 토큰 포함",
        has_detail_state_tokens(detail_html),
        "detail state tokens missing in light or dark CSS",
    )
    check(
        "/ HTML 은 데이터 렌더링에 innerHTML 대입을 사용하지 않음",
        avoids_data_inner_html(detail_html),
        "non-empty innerHTML assignment found",
    )


print("find_transcript 단일 세션 경로 최종 대체")
with tempfile.TemporaryDirectory(prefix="orca dashboard sole transcript ") as temporary_directory:
    transcript_directory = Path(temporary_directory)
    older_transcript = transcript_directory / "older.jsonl"
    newer_transcript = transcript_directory / "newer.jsonl"
    write_transcript(older_transcript, "서로 다른 이전 요청")
    write_transcript(newer_transcript, "서로 다른 최신 요청")
    os.utime(older_transcript, (100, 100))
    os.utime(newer_transcript, (200, 200))
    expect_equal(
        "①② 불일치해도 단일 세션 경로면 mtime 최신 transcript 선택",
        lambda: dashboard.find_transcript(
            str(transcript_directory),
            "덮어쓴 prompt",
            "빈 last message",
            sole_session=True,
        ),
        str(newer_transcript),
    )
    expect_equal(
        "①② 불일치하고 단일 세션 경로가 아니면 transcript 없음",
        lambda: dashboard.find_transcript(
            str(transcript_directory), "덮어쓴 prompt", "빈 last message"
        ),
        None,
    )

with tempfile.TemporaryDirectory(prefix="orca dashboard sole priority ") as temporary_directory:
    transcript_directory = Path(temporary_directory)
    prompt_match = transcript_directory / "older-prompt-match.jsonl"
    newest_fallback = transcript_directory / "newest-fallback.jsonl"
    write_transcript(prompt_match, "원래 사용자 요청")
    write_transcript(newest_fallback, "다른 사용자 요청")
    os.utime(prompt_match, (100, 100))
    os.utime(newest_fallback, (200, 200))
    expect_equal(
        "더 오래된 ① prompt 일치는 단일 세션 ③ 최신 대체보다 우선",
        lambda: dashboard.find_transcript(
            str(transcript_directory),
            "원래 사용자 요청",
            None,
            sole_session=True,
        ),
        str(prompt_match),
    )

with tempfile.TemporaryDirectory(prefix="orca dashboard sole unreadable ") as temporary_directory:
    transcript_directory = Path(temporary_directory)
    next_latest = transcript_directory / "next-latest.jsonl"
    unreadable_latest = transcript_directory / "unreadable-latest.jsonl"
    write_transcript(next_latest, "읽을 수 있는 transcript")
    unreadable_latest.mkdir()
    os.utime(next_latest, (100, 100))
    os.utime(unreadable_latest, (200, 200))
    expect_equal(
        "단일 세션 ③ 최신 transcript 읽기 실패 시 다음 최신 선택",
        lambda: dashboard.find_transcript(
            str(transcript_directory), None, None, sole_session=True
        ),
        str(next_latest),
    )

with tempfile.TemporaryDirectory(prefix="orca dashboard sole all unreadable ") as temporary_directory:
    transcript_directory = Path(temporary_directory)
    failed_candidate = transcript_directory / "only-unreadable.jsonl"
    failed_candidate.mkdir()
    sole_unreadable = transcript_read_error_observation(
        lambda: dashboard.find_transcript(
            str(transcript_directory), None, None, sole_session=True
        )
    )
    check(
        "단일 세션 ③에서 읽기 가능한 파일이 하나도 없으면 TranscriptReadError",
        transcript_error_matches(sole_unreadable, failed_candidate),
        f"observation={sole_unreadable!r}",
    )

expect_equal(
    "단일 세션이어도 transcript 디렉토리가 없으면 None",
    lambda: dashboard.find_transcript(
        "/definitely/missing/orca-dashboard-sole-transcripts",
        "불일치 prompt",
        None,
        sole_session=True,
    ),
    None,
)

with tempfile.TemporaryDirectory(prefix="orca dashboard sole empty keys ") as temporary_directory:
    transcript_directory = Path(temporary_directory)
    older_transcript = transcript_directory / "older.jsonl"
    newer_transcript = transcript_directory / "newer.jsonl"
    write_transcript(older_transcript, "이전 요청")
    write_transcript(newer_transcript, "최신 요청")
    os.utime(older_transcript, (100, 100))
    os.utime(newer_transcript, (200, 200))
    expect_equal(
        "prompt·last_message 모두 None이어도 단일 세션 경로면 mtime 최신 선택",
        lambda: dashboard.find_transcript(
            str(transcript_directory), None, None, sole_session=True
        ),
        str(newer_transcript),
    )


R24_ORCA_STUB = r'''#!/usr/bin/env python3
import json
import os
import sys

arguments = sys.argv[1:]
if arguments[-1:] == ["--json"]:
    arguments = arguments[:-1]

mode = os.environ["R24_STUB_MODE"]
worktree_path = "/tmp/r24-worktree"
agent_count = 0 if mode == "unique-terminal" else (2 if mode == "two-agents" else 1)
agents = []
terminals = []
for index in range(agent_count):
    suffix = str(index + 1)
    agents.append({
        "paneKey": "tab-r24-" + suffix + ":leaf-r24-" + suffix,
        "parentPaneKey": None,
        "state": "done",
        "agentType": "codex",
        "prompt": "transcript 요청과 불일치하는 하위 codex persona " + suffix,
        "lastAssistantMessage": "",
        "toolName": "Bash",
        "toolInput": "python3 worker.py",
        "interrupted": False,
        "mainAgent": {"state": "done", "stateStartedAt": 1980000},
        "stateStartedAt": 1985000,
        "updatedAt": 1999000 + index
    })
    terminals.append({
        "handle": "term-r24-" + suffix,
        "worktreeId": "wt-r24",
        "worktreePath": worktree_path,
        "branch": "refs/heads/feat/r24",
        "tabId": "tab-r24-" + suffix,
        "leafId": "leaf-r24-" + suffix,
        "title": "✳ R24 agent " + suffix,
        "connected": True,
        "lastOutputAt": 1999000 + index,
        "preview": "fixture ready"
    })

if mode == "unique-terminal":
    terminals.append({
        "handle": "term-r24-terminal",
        "worktreeId": "wt-r24",
        "worktreePath": worktree_path,
        "branch": "refs/heads/feat/r24",
        "tabId": "tab-r24-terminal",
        "leafId": "leaf-r24-terminal",
        "title": "✳ R24 terminal session",
        "connected": True,
        "lastOutputAt": 1999000,
        "preview": "terminal fixture ready"
    })

if arguments == ["worktree", "ps"]:
    result = {"worktrees": [{
        "worktreeId": "wt-r24",
        "repoId": "repo-r24",
        "repo": "acme/r24",
        "displayName": "R24 dashboard",
        "path": worktree_path,
        "branch": "refs/heads/feat/r24",
        "isArchived": False,
        "workspaceStatus": "clean",
        "comment": "",
        "liveTerminalCount": len(terminals),
        "lastOutputAt": 1999000,
        "linkedPR": None,
        "agents": agents
    }]}
elif arguments == ["terminal", "list"]:
    result = {"terminals": terminals}
elif arguments[:2] == ["terminal", "read"]:
    handle = arguments[arguments.index("--terminal") + 1]
    result = {"terminal": {"handle": handle, "tail": ["⏺ fixture ready"]}}
else:
    print(json.dumps({"ok": False, "error": "unexpected arguments: " + repr(arguments)}))
    raise SystemExit(1)

print(json.dumps({"ok": True, "result": result}))
'''


def r24_session_detail(mode, session_id):
    with tempfile.TemporaryDirectory(prefix="orca dashboard r24 serve ") as temporary_directory:
        temporary_root = Path(temporary_directory)
        stub_path = temporary_root / "orca r24 fixture.py"
        stub_path.write_text(R24_ORCA_STUB, encoding="utf-8")
        projects_root = temporary_root / "claude-projects"
        transcript_directory = Path(
            dashboard.transcript_dir(str(projects_root), "/tmp/r24-worktree")
        )
        transcript_directory.mkdir(parents=True)
        write_transcript(transcript_directory / "available.jsonl", "실제 transcript 요청")
        environment = os.environ.copy()
        environment["ORCA_CLI_COMMAND"] = shlex.join([sys.executable, str(stub_path)])
        environment["CLAUDE_PROJECTS_DIR"] = str(projects_root)
        environment["R24_STUB_MODE"] = mode
        environment["ORCA_DASHBOARD_HISTORY_DIR"] = str(
            temporary_root / "history"
        )
        port = unused_local_port()
        process = subprocess.Popen(
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
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            expected_count = 2 if mode == "two-agents" else 1
            ready, ready_error = wait_for_snapshot(
                process,
                port,
                lambda payload: len(payload.get("sessions", [])) == expected_count,
                timeout=5,
            )
            if ready is None:
                return None, ready_error
            response = http_response(
                f"http://127.0.0.1:{port}/api/session?id={session_id}"
            )
            try:
                payload = json.loads(response[2])
            except json.JSONDecodeError:
                payload = None
            return payload, f"status={response[0]}, payload={payload!r}"
        finally:
            stop_process(process)


print("serve 단일 세션 경로 transcript 최종 대체")
unique_agent_detail, unique_agent_error = r24_session_detail(
    "unique-agent", "tab-r24-1:leaf-r24-1"
)
check(
    "path 유일 agent 세션은 prompt 불일치해도 /api/session transcript true",
    isinstance(unique_agent_detail, dict)
    and unique_agent_detail.get("transcript") is True,
    unique_agent_error,
)

two_agent_detail, two_agent_error = r24_session_detail(
    "two-agents", "tab-r24-1:leaf-r24-1"
)
check(
    "같은 path 에 세션 2개면 /api/session transcript false",
    isinstance(two_agent_detail, dict)
    and two_agent_detail.get("transcript") is False,
    two_agent_error,
)

unique_terminal_detail, unique_terminal_error = r24_session_detail(
    "unique-terminal", "term-r24-terminal"
)
check(
    "path 유일 kind terminal 세션도 /api/session transcript true",
    isinstance(unique_terminal_detail, dict)
    and unique_terminal_detail.get("transcript") is True,
    unique_terminal_error,
)


print("serve transcript 읽기 실패 노출")
with tempfile.TemporaryDirectory(prefix="orca dashboard r30 serve ") as temporary_directory:
    temporary_root = Path(temporary_directory)
    read_failure_env = fixture_environment(temporary_directory)
    projects_root = temporary_root / "claude-projects"
    transcript_directory = Path(
        dashboard.transcript_dir(str(projects_root), "/tmp/wt-stub")
    )
    transcript_directory.mkdir(parents=True)
    failed_candidate = transcript_directory / "unreadable.jsonl"
    failed_candidate.mkdir()
    read_failure_env["CLAUDE_PROJECTS_DIR"] = str(projects_root)
    read_failure_port = unused_local_port()
    read_failure_process = subprocess.Popen(
        [
            sys.executable,
            str(DASHBOARD_PATH),
            "serve",
            "--port",
            str(read_failure_port),
            "--interval",
            "0.1",
        ],
        cwd=ROOT,
        env=read_failure_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    read_failure_ready = None
    read_failure_ready_error = "server did not become ready"
    read_failure_response = None
    try:
        read_failure_ready, read_failure_ready_error = wait_for_snapshot(
            read_failure_process,
            read_failure_port,
            lambda payload: any(
                session.get("id") == "tab-stub:leaf-stub"
                for session in payload.get("sessions", [])
            ),
            timeout=5,
        )
        if read_failure_ready is not None:
            read_failure_response = http_response(
                f"http://127.0.0.1:{read_failure_port}/api/session?id=tab-stub:leaf-stub"
            )
    finally:
        stop_process(read_failure_process)

    read_failure_payload = None
    if read_failure_response is not None:
        try:
            read_failure_payload = json.loads(read_failure_response[2])
        except json.JSONDecodeError:
            pass
    check(
        "/api/session transcript 읽기 실패는 200 + transcript false + transcriptError 문자열",
        read_failure_response is not None
        and read_failure_response[0] == 200
        and isinstance(read_failure_payload, dict)
        and read_failure_payload.get("transcript") is False
        and isinstance(read_failure_payload.get("transcriptError"), str)
        and bool(read_failure_payload["transcriptError"]),
        read_failure_ready_error
        if read_failure_ready is None
        else f"response={read_failure_response!r}, payload={read_failure_payload!r}",
    )


HISTORY_PIPELINES = {
    "private-implement": list(range(1, 11)),
    "private-roadmap": list(range(9)),
}
HISTORY_STEP_TITLES = {
    "private-implement": {step: f"구현 {step}" for step in range(1, 11)},
    "private-roadmap": {step: f"로드맵 {step}" for step in range(9)},
}


def history_timestamp(offset):
    minute, second = divmod(offset, 60)
    return f"2026-10-07T10:{minute:02d}:{second:02d}.000Z"


def history_record(record_type, offset, content=None, *, uuid=None, attachment=None):
    value = {"type": record_type, "timestamp": history_timestamp(offset)}
    if uuid is not None:
        value["uuid"] = uuid
    if attachment is not None:
        value["attachment"] = attachment
    else:
        value["message"] = {"content": content}
    return json.dumps(value, ensure_ascii=False)


def queued_command(offset, mode, prompt, *, uuid=None):
    return history_record(
        "attachment",
        offset,
        uuid=uuid,
        attachment={
            "type": "queued_command",
            "commandMode": mode,
            "prompt": prompt,
        },
    )


def assistant_text(offset, text, *, uuid=None):
    return history_record(
        "assistant", offset, [{"type": "text", "text": text}], uuid=uuid
    )


def tool_use(offset, tool_id, name, tool_input, *, uuid=None):
    return history_record(
        "assistant",
        offset,
        [{"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}],
        uuid=uuid,
    )


def slash_request(pipeline, arguments):
    return (
        f"<command-message>{pipeline}</command-message>\n"
        f"<command-name>/{pipeline}</command-name>\n"
        f"<command-args>{arguments}</command-args>"
    )


print("H1 요청 판정")
queued_prompt_lines = [
    queued_command(0, "prompt", "큐에 넣은 실제 요청", uuid="queued-request"),
]
expect_equal(
    "queued_command prompt 는 parse_transcript prompt 로 수집",
    lambda: dashboard.parse_transcript(queued_prompt_lines)["prompts"],
    [{"at": utc_ms(history_timestamp(0)), "text": "큐에 넣은 실제 요청"}],
)
expect_predicate(
    "queued_command prompt 는 작업 시작 요청으로 분할",
    lambda: dashboard.split_work_items(
        queued_prompt_lines, pipelines=HISTORY_PIPELINES
    ),
    lambda items: len(items) == 1
    and items[0]["id"] == "queued-request"
    and items[0]["title"] == "큐에 넣은 실제 요청"
    and items[0]["requestCount"] == 1,
    "one work item created from the measured attachment shape",
)

queued_failure_lines = [
    tool_use(
        1,
        "toolu-queued-failure",
        "Bash",
        {"command": "false", "description": "큐 알림 셸", "run_in_background": True},
    ),
    queued_command(
        2,
        "task-notification",
        notification(
            "toolu-queued-failure",
            "failed",
            'Background command "false" failed (exit code 2)',
        ),
    ),
]
expect_predicate(
    "queued_command task-notification 은 백그라운드 셸을 failed 로 종료",
    lambda: dashboard.parse_transcript(queued_failure_lines)["tasks"],
    lambda tasks: len(tasks) == 1
    and tasks[0]["state"] == "failed"
    and tasks[0]["endedAt"] == utc_ms(history_timestamp(2)),
    "failed task with attachment notification endedAt",
)

private_command = slash_request("private-implement", "히스토리 기능을 구현해 주세요")
excluded_request_lines = [
    history_record("user", 3, "<command-name>/clear</command-name>"),
    history_record("user", 4, "<command-name>/model</command-name>"),
    history_record("user", 5, "<local-command-stdout>ok</local-command-stdout>"),
    history_record("user", 6, "<local-command-caveat>local only</local-command-caveat>"),
    history_record("user", 7, "[Request interrupted by user for tool use]"),
    history_record("user", 8, "Base directory for this skill: /tmp/skill"),
    history_record(
        "user",
        9,
        "This session is being continued from a previous conversation that ran out of context.",
    ),
    history_record("user", 10, private_command, uuid="private-command"),
    history_record("user", 11, "후속 실제 요청으로 충분히 긴 문장입니다", uuid="actual-request"),
    history_record("user", 12, "<command-name>/clear</command-name>"),
]
expect_equal(
    "로컬 명령·interrupt·스킬 주입은 제외하고 private- 슬래시는 요청으로 유지",
    lambda: [
        prompt["text"]
        for prompt in dashboard.parse_transcript(excluded_request_lines)["prompts"]
    ],
    [
        "<command-message>private-implement</command-message>",
        "후속 실제 요청으로 충분히 긴 문장입니다",
    ],
)

with tempfile.TemporaryDirectory(prefix="orca dashboard h1 transcript ") as temporary_directory:
    transcript_directory = Path(temporary_directory)
    request_path = transcript_directory / "request.jsonl"
    request_path.write_text("\n".join(excluded_request_lines) + "\n", encoding="utf-8")
    queued_path = transcript_directory / "queued.jsonl"
    queued_path.write_text("\n".join(queued_prompt_lines) + "\n", encoding="utf-8")
    os.utime(request_path, (100, 100))
    os.utime(queued_path, (200, 200))
    expect_equal(
        "find_transcript ①은 제외 요청 뒤의 마지막 실제 요청으로 일치",
        lambda: dashboard.find_transcript(
            str(transcript_directory), "후속 실제 요청으로 충분히 긴 문장입니다"
        ),
        str(request_path),
    )
    expect_equal(
        "find_transcript ①은 queued_command prompt 실측 구조로 일치",
        lambda: dashboard.find_transcript(
            str(transcript_directory), "큐에 넣은 실제 요청"
        ),
        str(queued_path),
    )


print("H2 작업 분할")


def active_pipeline_items():
    lines = [
        history_record(
            "user", 20, "세션 히스토리 기능을 구현해 주세요", uuid="active-start"
        ),
        tool_use(
            21,
            "toolu-skill-active",
            "Skill",
            {"skill": "private-implement", "args": "세션 히스토리"},
        ),
        history_record(
            "user",
            22,
            [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu-ask-user",
                    "content": "Your questions have been answered: 승인",
                }
            ],
        ),
        history_record(
            "user", 23, "중간에 이 방식이 안전한지 설명해 주세요", uuid="question"
        ),
        queued_command(24, "prompt", "승인", uuid="approval"),
    ]
    return dashboard.split_work_items(lines, pipelines=HISTORY_PIPELINES)


expect_predicate(
    "활성 파이프라인 중 질문·승인은 귀속되고 AskUserQuestion tool_result 는 요청 아님",
    active_pipeline_items,
    lambda items: len(items) == 1
    and items[0]["pipeline"] == "private-implement"
    and items[0]["requestCount"] == 3,
    "one active pipeline item with three requests",
)


def pipeline_boundary_items():
    lines = [
        history_record("user", 30, "파이프라인 경계를 검증합니다", uuid="boundary-start"),
        tool_use(
            31,
            "toolu-boundary-skill",
            "Skill",
            {"skill": "private-implement", "args": "경계"},
        ),
        tool_use(
            32,
            "toolu-run-one",
            "Bash",
            {"command": "R=runs/private-implement/20261007-one && mkdir -p $R"},
        ),
        tool_use(
            33,
            "toolu-run-one-again",
            "Bash",
            {"command": "mkdir -p runs/private-implement/20261007-one/red"},
        ),
        tool_use(
            34,
            "toolu-run-two",
            "Bash",
            {"command": "mkdir -p runs/private-implement/20261007-two"},
            uuid="run-two",
        ),
        tool_use(
            35,
            "toolu-other-pipeline",
            "Skill",
            {"skill": "private-roadmap", "args": "새 계획"},
            uuid="other-pipeline",
        ),
    ]
    return dashboard.split_work_items(lines, pipelines=HISTORY_PIPELINES)


expect_predicate(
    "같은 s3 run 은 귀속하고 다른 run id·다른 pipeline 은 각각 분할",
    pipeline_boundary_items,
    lambda items: len(items) == 3
    and [item["pipeline"] for item in items]
    == ["private-implement", "private-implement", "private-roadmap"]
    and [item["runId"] for item in items[:2]]
    == [
        "runs/private-implement/20261007-one",
        "runs/private-implement/20261007-two",
    ]
    and [item["id"] for item in items] == ["boundary-start", "run-two", "other-pipeline"],
    "three items split at a different run id and a different pipeline",
)

expect_predicate(
    "파이프라인 없는 미확정 작업의 Skill 호출은 분할 없이 pipeline 채택",
    lambda: dashboard.split_work_items(
        [
            history_record("user", 40, "구현을 시작해 주세요", uuid="adopt-start"),
            tool_use(
                41,
                "toolu-adopt",
                "Skill",
                {"skill": "private-implement", "args": "구현"},
            ),
        ],
        pipelines=HISTORY_PIPELINES,
    ),
    lambda items: len(items) == 1
    and items[0]["id"] == "adopt-start"
    and items[0]["pipeline"] == "private-implement",
    "one adopted pipeline item",
)


def request_boundary_items():
    return dashboard.split_work_items(
        [
            history_record(
                "user", 45, "첫 번째 독립 작업을 상세히 처리해 주세요", uuid="request-one"
            ),
            history_record("user", 46, "승인", uuid="request-one-followup"),
            history_record("user", 46, "머지해", uuid="request-one-merge"),
            queued_command(
                47,
                "prompt",
                "두 번째 독립 작업을 상세히 처리해 주세요",
                uuid="request-two",
            ),
            history_record("user", 48, "1", uuid="request-two-followup"),
        ],
        pipelines=HISTORY_PIPELINES,
    )


expect_predicate(
    "파이프라인 밖 긴 요청마다 분할하고 짧은 후속은 직전 작업에 병합",
    request_boundary_items,
    lambda items: len(items) == 2
    and [item["id"] for item in items] == ["request-one", "request-two"]
    and [item["requestCount"] for item in items] == [3, 2],
    "two items with short 승인·머지해·1 follow-ups merged",
)

long_title = "가" * 90
title_items_action = lambda: dashboard.split_work_items(
    [
        history_record("user", 50, f"\n\n{long_title}\n둘째 줄", uuid="long-title"),
        assistant_text(50, "첫 번째 작업을 모두 완료했습니다"),
        history_record(
            "user",
            51,
            slash_request("private-roadmap", "분기별 계획을 작성해 주세요"),
            uuid="slash-title",
        ),
    ],
    pipelines=HISTORY_PIPELINES,
)
expect_predicate(
    "title 은 첫 의미 있는 줄 80자, 슬래시는 pipeline 과 command-args 조합",
    title_items_action,
    lambda items: len(items) == 2
    and items[0]["title"] == long_title[:80]
    and items[1]["title"] == "/private-roadmap 분기별 계획을 작성해 주세요",
    "contract titles for plain and slash requests",
)


def stepped_work_items():
    return dashboard.split_work_items(
        [
            history_record(
                "user",
                55,
                slash_request("private-implement", "단계 추적"),
                uuid="stepped-work",
            ),
            assistant_text(56, "현재 Step 1 진행 중입니다. 다음은 Step 4입니다."),
            assistant_text(57, "현재 Step 3 검증 중입니다."),
            assistant_text(58, "Step 3 검증을 계속합니다."),
            assistant_text(59, "현재 Step 7 진행 중입니다."),
        ],
        pipelines=HISTORY_PIPELINES,
        step_titles=HISTORY_STEP_TITLES,
    )


expect_predicate(
    "Step 변화는 예고·연속 중복을 제외하고 title·70% basis 를 보존",
    stepped_work_items,
    lambda items: len(items) == 1
    and set(items[0])
    == {
        "id",
        "title",
        "startedAt",
        "endedAt",
        "requestCount",
        "pipeline",
        "runId",
        "stepPath",
        "finalStep",
        "steps",
        "progress",
        "result",
        "subagents",
        "backgroundShells",
        "failedTasks",
    }
    and items[0]["stepPath"] == [1, 3, 7]
    and items[0]["finalStep"] == 7
    and items[0]["steps"]
    == [
        {"at": utc_ms(history_timestamp(56)), "step": 1, "title": "구현 1"},
        {"at": utc_ms(history_timestamp(57)), "step": 3, "title": "구현 3"},
        {"at": utc_ms(history_timestamp(59)), "step": 7, "title": "구현 7"},
    ]
    and items[0]["progress"]
    == {
        "percent": 70,
        "basis": "/private-implement Step 7 (7/10단계 진행 중)",
    },
    "stepPath [1, 3, 7], titled steps, and 70 percent",
)


def result_work_items():
    return dashboard.split_work_items(
        [
            history_record("user", 65, "완료될 첫 번째 작업 요청입니다", uuid="completed-work"),
            assistant_text(66, "요청한 변경을 모두 완료했습니다"),
            history_record("user", 67, "설명만 필요한 두 번째 질문입니다", uuid="answered-work"),
            assistant_text(68, "질문의 배경과 선택지를 설명합니다"),
            history_record("user", 69, "중단될 세 번째 작업 요청입니다", uuid="interrupted-work"),
            history_record("user", 70, "[Request interrupted by user for tool use]"),
            history_record("user", 71, "현재 진행 중인 마지막 작업입니다", uuid="running-work"),
        ],
        pipelines=HISTORY_PIPELINES,
    )


expect_equal(
    "작업 결과는 completed·answered·interrupted·in_progress 4값",
    lambda: [item["result"] for item in result_work_items()],
    ["completed", "answered", "interrupted", "in_progress"],
)
expect_equal(
    "work_summary 는 결과 4값을 모두 집계",
    lambda: dashboard.work_summary(result_work_items()),
    {
        "total": 4,
        "completed": 1,
        "inProgress": 1,
        "answered": 1,
        "interrupted": 1,
    },
)


def interrupted_pipeline_items():
    return dashboard.split_work_items(
        [
            history_record(
                "user",
                75,
                slash_request("private-implement", "중단 basis"),
                uuid="interrupted-pipeline",
            ),
            assistant_text(76, "현재 Step 3 진행 중입니다."),
            tool_use(
                77,
                "toolu-roadmap-boundary",
                "Skill",
                {"skill": "private-roadmap", "args": "다른 파이프라인"},
                uuid="roadmap-boundary",
            ),
        ],
        pipelines=HISTORY_PIPELINES,
    )


expect_predicate(
    "마지막 Step 이 아닌 파이프라인 작업은 중단 결과와 중단 basis 사용",
    interrupted_pipeline_items,
    lambda items: items[0]["result"] == "interrupted"
    and items[0]["progress"]
    == {
        "percent": 30,
        "basis": "/private-implement Step 3 (3/10단계에서 중단)",
    },
    "interrupted step 3 progress basis",
)


def task_count_items():
    lines = [
        history_record(
            "user",
            80,
            slash_request("private-implement", "도구 수 집계"),
            uuid="counted-work",
        ),
        tool_use(
            81,
            "toolu-agent-counted",
            "Agent",
            {"description": "에이전트", "prompt": "조사", "subagent_type": "Explore"},
        ),
        tool_use(
            82,
            "toolu-task-counted",
            "Task",
            {"description": "태스크", "prompt": "검증", "subagent_type": "general-purpose"},
        ),
        tool_use(
            83,
            "toolu-shell-counted",
            "Bash",
            {"command": "false", "description": "실패 셸", "run_in_background": True},
        ),
        tool_use(
            84,
            "toolu-count-boundary",
            "Skill",
            {"skill": "private-roadmap", "args": "경계"},
            uuid="count-boundary",
        ),
        queued_command(
            85,
            "task-notification",
            notification(
                "toolu-shell-counted",
                "failed",
                'Background command "false" failed (exit code 1)',
            ),
        ),
    ]
    return dashboard.split_work_items(lines, pipelines=HISTORY_PIPELINES)


expect_predicate(
    "subagents·backgroundShells·failedTasks 는 시작 작업 기준으로 집계",
    task_count_items,
    lambda items: items[0]["subagents"] == 2
    and items[0]["backgroundShells"] == 1
    and items[0]["failedTasks"] == 1
    and items[1]["failedTasks"] == 0,
    "2 subagents, 1 background shell, 1 failed task on the origin work",
)


def broken_line_items(include_broken):
    lines = [
        history_record("user", 90, "깨진 줄 전의 작업 요청입니다", uuid="broken-one"),
        history_record("user", 91, "깨진 줄 뒤의 별도 작업 요청입니다", uuid="broken-two"),
    ]
    if include_broken:
        lines[1:1] = [
            "{broken json",
            json.dumps({"type": "assistant", "message": {"content": []}}),
        ]
    return dashboard.split_work_items(lines, pipelines=HISTORY_PIPELINES)


expect_equal(
    "깨진 JSON·timestamp 없는 줄은 건너뛰어 분할 결과를 바꾸지 않음",
    lambda: broken_line_items(True),
    broken_line_items(False) if hasattr(dashboard, "split_work_items") else [],
)


def preserved_progress_items():
    return dashboard.split_work_items(
        [
            history_record(
                "user",
                95,
                slash_request("private-implement", "이전 작업"),
                uuid="preserved-work",
            ),
            assistant_text(96, "현재 Step 7 진행 중입니다."),
            tool_use(
                97,
                "toolu-new-roadmap",
                "Skill",
                {"skill": "private-roadmap", "args": "새 작업"},
                uuid="new-roadmap",
            ),
            assistant_text(98, "private-roadmap 현재 Step 8 진행 중입니다."),
        ],
        pipelines=HISTORY_PIPELINES,
    )


expect_predicate(
    "다음 작업 Step 변화 뒤에도 이전 작업의 stepPath·진행률을 보존",
    preserved_progress_items,
    lambda items: len(items) == 2
    and items[0]["stepPath"] == [7]
    and items[0]["progress"]["percent"] == 70
    and items[1]["stepPath"] == [8],
    "previous 70 percent remains after the next work reaches Step 8",
)


print("H3 관측 히스토리")
expect_equal(
    "히스토리 상수는 스키마·추적 필드·상한·압축 임계값 계약과 일치",
    lambda: {
        "version": dashboard.HISTORY_SCHEMA_VERSION,
        "fields": dashboard.HISTORY_TRACKED_FIELDS,
        "points": dashboard.HISTORY_POINTS_PER_SESSION,
        "compact": dashboard.HISTORY_COMPACT_LINES,
    },
    {
        "version": 1,
        "fields": ("status", "percent", "basis", "pipeline", "step"),
        "points": 500,
        "compact": 20_000,
    },
)


def history_session(session_id="history-session", **overrides):
    value = {
        "id": session_id,
        "name": "히스토리 세션",
        "path": "/tmp/history-worktree",
        "agentType": "claude",
        "status": "running",
        "progress": {"percent": 30, "basis": "Step 근거"},
        "checklist": {
            "pipeline": "private-implement",
            "steps": [
                {"number": 1, "title": "준비", "state": "done"},
                {"number": 3, "title": "검증", "state": "current"},
            ],
        },
    }
    value.update(overrides)
    return value


expect_equal(
    "history_point 는 공개 세션 필드와 현재 pipeline·step 을 평탄화",
    lambda: dashboard.history_point(history_session(), 1234),
    {
        "v": 1,
        "at": 1234,
        "sessionId": "history-session",
        "name": "히스토리 세션",
        "path": "/tmp/history-worktree",
        "agentType": "claude",
        "status": "running",
        "percent": 30,
        "basis": "Step 근거",
        "pipeline": "private-implement",
        "step": 3,
    },
)


def history_change_result():
    first = dashboard.history_point(history_session("unchanged"), 100)
    changed_before = dashboard.history_point(history_session("changed"), 100)
    snapshot = {
        "error": None,
        "sessions": [
            history_session("unchanged", name="표시명만 변경"),
            history_session(
                "changed", progress={"percent": 40, "basis": "새 근거"}
            ),
            history_session("new"),
        ],
    }
    return dashboard.history_changes(
        {"unchanged": first, "changed": changed_before}, snapshot, 200
    )


expect_predicate(
    "history_changes 는 추적 필드가 바뀐 세션과 신규 세션만 반환",
    history_change_result,
    lambda points: [point["sessionId"] for point in points] == ["changed", "new"]
    and all(point["at"] == 200 for point in points),
    "changed and new sessions only",
)
expect_equal(
    "같은 snapshot 연속 관측은 변화 없음",
    lambda: dashboard.history_changes(
        {"same": dashboard.history_point(history_session("same"), 100)},
        {"error": None, "sessions": [history_session("same")]},
        200,
    ),
    [],
)
expect_equal(
    "error snapshot 은 히스토리 기록 대상 없음",
    lambda: dashboard.history_changes(
        {}, {"error": "수집 실패", "sessions": [history_session()]}, 200
    ),
    [],
)


def parse_history_fixture():
    valid_lines = [
        json.dumps(
            {
                "v": 1,
                "at": at,
                "sessionId": "capped",
                "status": "running",
                "percent": at,
            }
        )
        for at in range(502, 0, -1)
    ]
    invalid_lines = [
        "{broken",
        json.dumps([]),
        json.dumps({"v": 2, "at": 1, "sessionId": "wrong-version"}),
        json.dumps({"v": 1, "at": 1, "sessionId": ""}),
        json.dumps({"v": 1, "at": "1", "sessionId": "bad-at"}),
    ]
    return dashboard.parse_history(invalid_lines + valid_lines)


expect_predicate(
    "parse_history 는 잘못된 줄을 건너뛰고 세션별 시간순 마지막 500개 유지",
    parse_history_fixture,
    lambda points: list(points) == ["capped"]
    and len(points["capped"]) == 500
    and points["capped"][0]["at"] == 3
    and points["capped"][-1]["at"] == 502,
    "only valid capped points sorted from at=3 through at=502",
)


print("H4 HistoryStore")
expect_equal(
    "history_path 는 비어 있지 않은 env 디렉토리를 우선",
    lambda: dashboard.history_path(
        {"ORCA_DASHBOARD_HISTORY_DIR": "/tmp/custom-history"}
    ),
    "/tmp/custom-history/history.jsonl",
)
expect_equal(
    "history_path 기본값은 __file__ 과 무관한 expanduser 홈 하위",
    lambda: dashboard.history_path({}),
    str(Path.home() / ".harness" / "runs" / "orca-dashboard" / "history.jsonl"),
)
expect_equal(
    "history_path 는 빈 env 값을 기본 expanduser 경로로 처리",
    lambda: dashboard.history_path({"ORCA_DASHBOARD_HISTORY_DIR": ""}),
    str(Path.home() / ".harness" / "runs" / "orca-dashboard" / "history.jsonl"),
)


def history_store_restart_observation():
    with tempfile.TemporaryDirectory(prefix="orca dashboard history restart ") as temporary_directory:
        path = Path(temporary_directory) / "history.jsonl"
        snapshot = {"error": None, "sessions": [history_session()]}
        first_store = dashboard.HistoryStore(str(path))
        first_warnings = first_store.record(snapshot, 100)
        second_store = dashboard.HistoryStore(str(path))
        load_warnings = second_store.load()
        before = second_store.points("history-session")
        duplicate_warnings = second_store.record(snapshot, 200)
        after = second_store.points("history-session")
        lines = path.read_text(encoding="utf-8").splitlines()
        return first_warnings, load_warnings, duplicate_warnings, before, after, lines


expect_predicate(
    "HistoryStore 는 재시작 load 후 같은 점을 중복 기록하지 않음",
    history_store_restart_observation,
    lambda result: result[0] == []
    and result[1] == []
    and result[2] == []
    and result[3] == result[4]
    and len(result[3]) == 1
    and len(result[5]) == 1,
    "one persisted point before and after restart",
)


def history_store_broken_tail_observation():
    with tempfile.TemporaryDirectory(prefix="orca dashboard history broken ") as temporary_directory:
        path = Path(temporary_directory) / "history.jsonl"
        path.write_text('{"v":1,"at":', encoding="utf-8")
        store = dashboard.HistoryStore(str(path))
        warnings = store.record(
            {"error": None, "sessions": [history_session("after-broken")]}, 300
        )
        reloaded = dashboard.HistoryStore(str(path))
        load_warnings = reloaded.load()
        return warnings, load_warnings, reloaded.points("after-broken"), path.read_bytes()


expect_predicate(
    "개행 없이 잘린 마지막 조각 뒤 기록은 새 줄로 온전히 복원",
    history_store_broken_tail_observation,
    lambda result: result[0] == []
    and result[1] == []
    and len(result[2]) == 1
    and b'\n{"v"' in result[3],
    "one valid point after the broken fragment and an inserted newline",
)


def history_store_write_failure_observation():
    with tempfile.TemporaryDirectory(prefix="orca dashboard history write failure ") as temporary_directory:
        blocker = Path(temporary_directory) / "not-a-directory"
        blocker.write_text("block", encoding="utf-8")
        store = dashboard.HistoryStore(str(blocker / "history.jsonl"))
        return store.record(
            {"error": None, "sessions": [history_session("write-failure")]}, 400
        )


expect_predicate(
    "HistoryStore 쓰기 실패는 예외 없이 history 기록 실패 warning",
    history_store_write_failure_observation,
    lambda warnings: len(warnings) == 1
    and warnings[0].startswith("history 기록 실패 ")
    and "history.jsonl" in warnings[0],
    "one history write warning containing the target path",
)


def history_store_read_failure_observation():
    with tempfile.TemporaryDirectory(prefix="orca dashboard history read failure ") as temporary_directory:
        store = dashboard.HistoryStore(temporary_directory)
        return store.load()


expect_predicate(
    "HistoryStore 읽기 실패는 history 읽기 실패 warning",
    history_store_read_failure_observation,
    lambda warnings: len(warnings) == 1
    and warnings[0].startswith("history 읽기 실패 "),
    "one history read warning",
)


def history_store_compaction_observation():
    with tempfile.TemporaryDirectory(prefix="orca dashboard history compact ") as temporary_directory:
        path = Path(temporary_directory) / "history.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for index in range(20_001):
                session_id = "compact-a" if index % 2 == 0 else "compact-b"
                handle.write(
                    json.dumps(
                        {
                            "v": 1,
                            "at": index,
                            "sessionId": session_id,
                            "status": "running",
                            "percent": index % 101,
                            "basis": "fixture",
                            "pipeline": None,
                            "step": None,
                        }
                    )
                    + "\n"
                )
        store = dashboard.HistoryStore(str(path))
        store.load()
        warnings = store.record(
            {"error": None, "sessions": [history_session("compact-new")]}, 30_000
        )
        reloaded = dashboard.HistoryStore(str(path))
        load_warnings = reloaded.load()
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        return warnings, load_warnings, line_count, {
            session_id: len(reloaded.points(session_id))
            for session_id in ("compact-a", "compact-b", "compact-new")
        }


expect_predicate(
    "압축 임계값 초과 시 세션별 상한만 남기고 재로드 결과 유지",
    history_store_compaction_observation,
    lambda result: result[0] == []
    and result[1] == []
    and result[2] == 1001
    and result[3] == {"compact-a": 500, "compact-b": 500, "compact-new": 1},
    "1001 compacted lines and 500/500/1 points after reload",
)


print("H5·H6 serve·API 연동")
with tempfile.TemporaryDirectory(prefix="orca dashboard snapshot no history ") as temporary_directory:
    snapshot_only_env = fixture_environment(temporary_directory)
    snapshot_only_process = subprocess.run(
        [sys.executable, str(DASHBOARD_PATH), "snapshot"],
        cwd=ROOT,
        env=snapshot_only_env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    check(
        "snapshot 서브커맨드는 성공해도 history.jsonl 을 기록하지 않음",
        snapshot_only_process.returncode == 0
        and not (
            Path(snapshot_only_env["ORCA_DASHBOARD_HISTORY_DIR"])
            / "history.jsonl"
        ).exists(),
        f"exit={snapshot_only_process.returncode}, stderr={snapshot_only_process.stderr[-500:]!r}",
    )

expect_equal(
    "build_detail 은 transcript 없어도 신규 API 키 4개를 항상 포함",
    lambda: {
        key: dashboard.build_detail(DETAIL_SESSION, None, now_ms=NOW_MS)[key]
        for key in ("workItems", "workSummary", "progressSeries", "historyWarnings")
    },
    {
        "workItems": [],
        "workSummary": {
            "total": 0,
            "completed": 0,
            "inProgress": 0,
            "answered": 0,
            "interrupted": 0,
        },
        "progressSeries": [],
        "historyWarnings": [],
    },
)


def snapshot_work_summary_key():
    sample_worktree = worktree(
        "wt-work-summary",
        agents=[
            agent(
                "tab-work-summary:leaf",
                prompt="work summary key",
                lastAssistantMessage="fixture",
            )
        ],
        liveTerminalCount=1,
    )
    sample_terminal = terminal(
        "term-work-summary", "wt-work-summary", "tab-work-summary", "leaf"
    )
    snapshot = dashboard.build_snapshot(
        [sample_worktree],
        [sample_terminal],
        {"term-work-summary": ["⏺ fixture"]},
        now_ms=NOW_MS,
        pipelines=HISTORY_PIPELINES,
    )
    return snapshot["sessions"][0]


expect_predicate(
    "snapshot 세션은 workSummary 키를 항상 가지며 기본 수집은 None",
    snapshot_work_summary_key,
    lambda session: "workSummary" in session and session["workSummary"] is None,
    "workSummary key with None when no transcript is connected",
)


HISTORY_SERVE_STUB = r'''#!/usr/bin/env python3
import json
import os
import sys

arguments = sys.argv[1:]
if arguments[-1:] == ["--json"]:
    arguments = arguments[:-1]

cycle_path = os.environ["HISTORY_STUB_CYCLE_FILE"]
if arguments == ["worktree", "ps"]:
    try:
        with open(cycle_path, encoding="utf-8") as handle:
            cycle = int(handle.read()) + 1
    except (FileNotFoundError, ValueError):
        cycle = 1
    with open(cycle_path, "w", encoding="utf-8") as handle:
        handle.write(str(cycle))
    step = 1 if cycle == 1 else 2
    result = {"worktrees": [{
        "worktreeId": "wt-history-serve",
        "repoId": "repo-history-serve",
        "repo": "acme/history",
        "displayName": "History serve",
        "path": "/tmp/h5-worktree",
        "branch": "refs/heads/feat/history",
        "isArchived": False,
        "workspaceStatus": "in-progress",
        "comment": "",
        "liveTerminalCount": 1,
        "lastOutputAt": 1791363251848 + cycle,
        "linkedPR": None,
        "agents": [{
            "paneKey": "tab-history:leaf-history",
            "parentPaneKey": None,
            "state": "working",
            "agentType": "claude",
            "prompt": "히스토리 누적 통합 요청",
            "lastAssistantMessage": "/private-implement Step %d 진행 중" % step,
            "toolName": "Bash",
            "toolInput": "python3 tests/test_orca_dashboard.py",
            "interrupted": False,
            "mainAgent": {"state": "working", "stateStartedAt": 1791362716595},
            "stateStartedAt": 1791362852461,
            "updatedAt": 1791363253026 + cycle
        }]
    }]}
elif arguments == ["terminal", "list"]:
    result = {"terminals": [{
        "handle": "term-history",
        "worktreeId": "wt-history-serve",
        "worktreePath": "/tmp/h5-worktree",
        "branch": "refs/heads/feat/history",
        "tabId": "tab-history",
        "leafId": "leaf-history",
        "title": "✳ History serve",
        "connected": True,
        "lastOutputAt": 1791363251848,
        "preview": "fixture"
    }]}
elif arguments[:2] == ["terminal", "read"]:
    try:
        with open(cycle_path, encoding="utf-8") as handle:
            cycle = int(handle.read())
    except (FileNotFoundError, ValueError):
        cycle = 1
    step = 1 if cycle == 1 else 2
    result = {"terminal": {
        "handle": "term-history",
        "tail": ["⏺ /private-implement Step %d 진행 중" % step]
    }}
else:
    print(json.dumps({"ok": False, "error": "unexpected arguments: " + repr(arguments)}))
    raise SystemExit(1)

print(json.dumps({"ok": True, "result": result}))
'''


def history_serve_environment(temporary_directory):
    temporary_root = Path(temporary_directory)
    stub_path = temporary_root / "orca history fixture.py"
    stub_path.write_text(HISTORY_SERVE_STUB, encoding="utf-8")
    projects_root = temporary_root / "claude-projects"
    transcript_directory = Path(
        dashboard.transcript_dir(str(projects_root), "/tmp/h5-worktree")
    )
    transcript_directory.mkdir(parents=True)
    transcript_lines = [
        history_record(
            "user",
            106,
            slash_request("private-roadmap", "먼저 완료할 작업"),
            uuid="serve-work-completed",
        ),
        assistant_text(107, "현재 Step 1 진행 중입니다."),
        assistant_text(108, "첫 번째 작업을 모두 완료했습니다"),
        history_record("user", 110, "히스토리 누적 통합 요청", uuid="serve-work-running"),
        tool_use(
            111,
            "toolu-serve-skill",
            "Skill",
            {"skill": "private-implement", "args": "히스토리"},
        ),
        assistant_text(112, "현재 Step 1 진행 중입니다."),
        assistant_text(113, "현재 Step 2 진행 중입니다."),
    ]
    (transcript_directory / "serve.jsonl").write_text(
        "\n".join(transcript_lines) + "\n", encoding="utf-8"
    )
    environment = os.environ.copy()
    environment["ORCA_CLI_COMMAND"] = shlex.join([sys.executable, str(stub_path)])
    environment["ORCA_DASHBOARD_HISTORY_DIR"] = str(temporary_root / "history")
    environment["CLAUDE_PROJECTS_DIR"] = str(projects_root)
    environment["HISTORY_STUB_CYCLE_FILE"] = str(temporary_root / "cycle.txt")
    return environment


def wait_for_history_lines(process, path, minimum, timeout):
    deadline = time.monotonic() + timeout
    detail = "history file was not created"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stderr = process.stderr.read() if process.stderr else ""
            return None, f"server exited {process.returncode}: {stderr[-800:]}"
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            detail = f"history lines={len(lines)}"
            if len(lines) >= minimum:
                return lines, ""
        except OSError as error:
            detail = f"{type(error).__name__}: {error}"
        time.sleep(0.03)
    return None, detail


def run_history_serve(port, environment):
    return subprocess.Popen(
        [
            sys.executable,
            str(DASHBOARD_PATH),
            "serve",
            "--port",
            str(port),
            "--interval",
            "0.15",
        ],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


with tempfile.TemporaryDirectory(prefix="orca dashboard history serve ") as temporary_directory:
    history_env = history_serve_environment(temporary_directory)
    history_path = Path(history_env["ORCA_DASHBOARD_HISTORY_DIR"]) / "history.jsonl"
    history_port = unused_local_port()
    history_process = run_history_serve(history_port, history_env)
    history_lines = None
    history_detail = "history server did not become ready"
    first_detail_payload = None
    first_snapshot_payload = None
    try:
        first_snapshot_payload, history_detail = wait_for_snapshot(
            history_process,
            history_port,
            lambda payload: any(
                session.get("id") == "tab-history:leaf-history"
                and isinstance(session.get("workSummary"), dict)
                for session in payload.get("sessions", [])
            ),
            timeout=6,
        )
        history_lines, line_error = wait_for_history_lines(
            history_process, history_path, 2, timeout=6
        )
        if history_lines is None:
            history_detail = line_error
        if first_snapshot_payload is not None and history_lines is not None:
            response = http_response(
                f"http://127.0.0.1:{history_port}/api/session?id=tab-history:leaf-history"
            )
            if response[0] == 200:
                first_detail_payload = json.loads(response[2])
    finally:
        stop_process(history_process)

    restart_port = unused_local_port()
    restart_process = run_history_serve(restart_port, history_env)
    restart_detail_payload = None
    restart_error = "restart server did not become ready"
    try:
        restart_snapshot, restart_error = wait_for_snapshot(
            restart_process,
            restart_port,
            lambda payload: any(
                session.get("id") == "tab-history:leaf-history"
                for session in payload.get("sessions", [])
            ),
            timeout=6,
        )
        if restart_snapshot is not None:
            response = http_response(
                f"http://127.0.0.1:{restart_port}/api/session?id=tab-history:leaf-history"
            )
            if response[0] == 200:
                restart_detail_payload = json.loads(response[2])
    finally:
        stop_process(restart_process)

    check(
        "serve 진행률 변화 2주기는 history.jsonl 에 정확히 2줄 기록",
        history_lines is not None
        and len(history_lines) == 2
        and all(json.loads(line)["sessionId"] == "tab-history:leaf-history" for line in history_lines),
        history_detail,
    )
    check(
        "serve /api/session 은 transcript·dashboard progressSeries 와 신규 키를 반환",
        isinstance(first_detail_payload, dict)
        and all(
            key in first_detail_payload
            for key in ("workItems", "workSummary", "progressSeries", "historyWarnings")
        )
        and first_detail_payload["workItems"]
        and first_detail_payload["workSummary"]["total"] == 2
        and {point["source"] for point in first_detail_payload["progressSeries"]}
        == {"transcript", "dashboard"}
        and {
            point["workId"]
            for point in first_detail_payload["progressSeries"]
            if point["source"] == "transcript"
        }
        == {"serve-work-completed", "serve-work-running"}
        and all(
            point["workId"] is None
            for point in first_detail_payload["progressSeries"]
            if point["source"] == "dashboard"
        )
        and len(
            [
                point
                for point in first_detail_payload["progressSeries"]
                if point["source"] == "dashboard"
            ]
        )
        == 2,
        history_detail if first_detail_payload is None else repr(first_detail_payload),
    )
    check(
        "serve 재시작 후 /api/session progressSeries 에 기존 관측 2점 유지",
        isinstance(restart_detail_payload, dict)
        and len(
            [
                point
                for point in restart_detail_payload.get("progressSeries", [])
                if point.get("source") == "dashboard"
            ]
        )
        == 2,
        restart_error if restart_detail_payload is None else repr(restart_detail_payload),
    )


with tempfile.TemporaryDirectory(prefix="orca dashboard history warning ") as temporary_directory:
    warning_root = Path(temporary_directory)
    warning_env = history_serve_environment(temporary_directory)
    blocked_history_directory = warning_root / "history-blocker"
    blocked_history_directory.write_text("not a directory", encoding="utf-8")
    warning_env["ORCA_DASHBOARD_HISTORY_DIR"] = str(blocked_history_directory)
    warning_port = unused_local_port()
    warning_process = run_history_serve(warning_port, warning_env)
    warning_snapshot = None
    warning_detail_payload = None
    warning_error = "history warning was not observed"
    try:
        warning_snapshot, warning_error = wait_for_snapshot(
            warning_process,
            warning_port,
            lambda payload: payload.get("error") is None
            and payload.get("sessions")
            and any("history 기록 실패" in warning for warning in payload.get("warnings", [])),
            timeout=6,
        )
        if warning_snapshot is not None:
            response = http_response(
                f"http://127.0.0.1:{warning_port}/api/session?id=tab-history:leaf-history"
            )
            if response[0] == 200:
                warning_detail_payload = json.loads(response[2])
    finally:
        stop_process(warning_process)
    check(
        "히스토리 기록 실패는 snapshot error 가 아니라 warnings 만 남기고 sessions 갱신",
        isinstance(warning_snapshot, dict)
        and warning_snapshot.get("error") is None
        and warning_snapshot.get("sessions")
        and any(
            "history 기록 실패" in warning
            for warning in warning_snapshot.get("warnings", [])
        )
        and any(
            "history 읽기 실패" in warning
            for warning in warning_snapshot.get("warnings", [])
        )
        and isinstance(warning_detail_payload, dict)
        and any(
            "history 기록 실패" in warning
            for warning in warning_detail_payload.get("historyWarnings", [])
        ),
        warning_error
        if warning_snapshot is None
        else f"snapshot={warning_snapshot!r}, detail={warning_detail_payload!r}",
    )


NODE_UI_HARNESS = r"""
class StubNode {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName;
    this.ownerDocument = ownerDocument;
    this.children = [];
    this.parentNode = null;
    this.attributes = {};
    this.dataset = {};
    this.style = {};
    this.className = "";
    this.hidden = false;
    this.listeners = {};
    this._text = "";
    this.classList = {
      toggle: (name, enabled) => {
        const names = new Set(this.className.split(/\s+/).filter(Boolean));
        if (enabled) names.add(name); else names.delete(name);
        this.className = [...names].join(" ");
      },
    };
  }
  set textContent(value) {
    this._text = value === null || value === undefined ? "" : String(value);
    this.children = [];
  }
  get textContent() {
    return this._text + this.children.map((child) => child.textContent).join("");
  }
  setAttribute(name, value) {
    const text = String(value);
    this.attributes[name] = text;
    if (name === "class") this.className = text;
    if (name === "id") {
      this.id = text;
      this.ownerDocument.nodesById.set(text, this);
    }
    if (name.startsWith("data-")) {
      const key = name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
      this.dataset[key] = text;
    }
  }
  appendChild(child) {
    child.parentNode = this;
    this.children.push(child);
    return child;
  }
  replaceChildren(...children) {
    this._text = "";
    this.children = [];
    for (const child of children) this.appendChild(child);
  }
  addEventListener(type, listener) {
    (this.listeners[type] ||= []).push(listener);
  }
  dispatchEvent(event) {
    event.target = this;
    event.currentTarget = this;
    if (!event.preventDefault) event.preventDefault = () => {};
    for (const listener of this.listeners[event.type] || []) listener(event);
    return true;
  }
}

class StubDocument {
  constructor() {
    this.nodesById = new Map();
    this.body = new StubNode("body", this);
    this.title = "Orca 세션 대시보드";
  }
  createElement(tagName) { return new StubNode(tagName, this); }
  createElementNS(_namespace, tagName) { return new StubNode(tagName, this); }
  createTextNode(text) {
    const node = new StubNode("#text", this);
    node.textContent = text;
    return node;
  }
  getElementById(id) { return this.nodesById.get(id) || null; }
  querySelectorAll(selector) {
    const key = selector === "[data-ago]" ? "ago" : selector === "[data-since]" ? "since" : null;
    if (!key) return [];
    const matches = [];
    const visit = (node) => {
      if (Object.prototype.hasOwnProperty.call(node.dataset, key)) matches.push(node);
      for (const child of node.children) visit(child);
    };
    visit(this.body);
    return matches;
  }
}

const document = new StubDocument();
function staticNode(id, parent) {
  const node = document.createElement(id === "back" ? "button" : "div");
  node.setAttribute("id", id);
  (parent || document.body).appendChild(node);
  return node;
}
const listView = staticNode("list-view");
const detailView = staticNode("detail-view");
detailView.hidden = true;
for (const id of ["updated", "banner"]) staticNode(id);
for (const id of ["kpi-total", "kpi-running", "kpi-waiting", "kpi-blocked", "cards",
  "shell-only-title", "shell-only-list", "no-terminal-title", "no-terminal-list"]) staticNode(id, listView);
staticNode("back", detailView);
staticNode("detail-body", detailView);

const windowListeners = {};
const window = {
  addEventListener(type, listener) { (windowListeners[type] ||= []).push(listener); },
  dispatchEvent(event) {
    for (const listener of windowListeners[event.type] || []) listener(event);
  },
  scrollTo() {},
};
let currentHash = "";
const location = {
  get hash() { return currentHash; },
  set hash(value) {
    const next = value ? (String(value).startsWith("#") ? String(value) : "#" + value) : "";
    if (next === currentHash) return;
    currentHash = next;
    queueMicrotask(() => window.dispatchEvent({type: "hashchange"}));
  },
};
const history = {length: 2, back() { location.hash = ""; }};
window.document = document;
window.location = location;
window.history = history;
globalThis.document = document;
globalThis.window = window;
globalThis.location = location;
globalThis.history = history;

const scheduledTimers = [];
globalThis.setInterval = () => 1;
globalThis.setTimeout = (callback) => { scheduledTimers.push(callback); return scheduledTimers.length; };

function session(id, name) {
  return {
    id, name, repo: "acme/dashboard", branch: "feat/ui", path: "/tmp/ui", kind: "agent",
    agentType: "claude", agentState: "done", mainState: "done", toolName: "Agent",
    status: "idle", reason: "응답 완료 — 다음 지시 대기", summary: {text: name + " 요약", source: "lastMessage"},
    progress: {percent: 50, basis: "테스트 진행률"}, checklist: null,
    workSummary: id === "C" ? null : {total: 4, completed: 1, inProgress: 1, answered: 1, interrupted: 1},
    lastOutputAt: 1900000, pr: null,
  };
}
const sessions = [session("A", "세션 A"), session("B", "세션 B"), session("C", "세션 C")];
const snapshotPayload = {
  generatedAt: 2000000, lastSuccessAt: 2000000, interval: 3, error: null, warnings: [],
  kpi: {total: 3, running: 0, waitingUser: 0, blockedOrStale: 0},
  sessions, shellOnly: [], noTerminal: [],
};
function detailPayload(id) {
  const selected = sessions.find((item) => item.id === id);
  const workItems = [
    {id: "work-completed", title: "완료한 이전 작업", startedAt: 100, endedAt: 110,
      requestCount: 1, pipeline: "private-implement", runId: null, stepPath: [1, 2], finalStep: 2,
      steps: [{at: 100, step: 1, title: "준비"}, {at: 105, step: 2, title: "구현"}],
      progress: {percent: 100, basis: "완료 보고"}, result: "completed",
      subagents: 1, backgroundShells: 2, failedTasks: 0},
    {id: "work-answered", title: "설명으로 끝난 작업", startedAt: 120, endedAt: 130,
      requestCount: 1, pipeline: null, runId: null, stepPath: [], finalStep: null, steps: [],
      progress: {percent: null, basis: "산정 불가"}, result: "answered",
      subagents: 0, backgroundShells: 0, failedTasks: 0},
    {id: "work-interrupted", title: "중단된 작업", startedAt: 140, endedAt: 150,
      requestCount: 1, pipeline: "private-roadmap", runId: null, stepPath: [3], finalStep: 3,
      steps: [{at: 145, step: 3, title: "검증"}],
      progress: {percent: 33, basis: "/private-roadmap Step 3 (3/9단계에서 중단)"}, result: "interrupted",
      subagents: 0, backgroundShells: 1, failedTasks: 1},
    {id: "work-running", title: "현재 진행 중인 최신 작업", startedAt: 200, endedAt: 240,
      requestCount: 2, pipeline: "private-implement", runId: "runs/private-implement/20261007-ui",
      stepPath: [1, 3, 7], finalStep: 7,
      steps: [{at: 200, step: 1, title: "준비"}, {at: 210, step: 3, title: "검증"}, {at: 240, step: 7, title: "마무리"}],
      progress: {percent: 70, basis: "/private-implement Step 7 (7/10단계 진행 중)"}, result: "in_progress",
      subagents: 2, backgroundShells: 1, failedTasks: 0},
  ];
  const progressSeries = id === "B" ? [
    {at: 100, percent: 10, basis: "한 점", source: "transcript", workId: "work-completed"},
  ] : [
    {at: 100, percent: 10, basis: "work 1 시작", source: "transcript", workId: "work-completed"},
    {at: 105, percent: 30, basis: "관측 시작", source: "dashboard", workId: null},
    {at: 110, percent: 100, basis: "완료 보고", source: "transcript", workId: "work-completed"},
    {at: 200, percent: 20, basis: "work 4 Step 2", source: "transcript", workId: "work-running"},
    {at: 210, percent: 30, basis: "work 4 Step 3", source: "transcript", workId: "work-running"},
    {at: 220, percent: null, basis: "산정 불가", source: "transcript", workId: "work-running"},
    {at: 230, percent: 60, basis: "work 4 Step 6", source: "transcript", workId: "work-running"},
    {at: 240, percent: 70, basis: "work 4 Step 7", source: "transcript", workId: "work-running"},
    {at: 245, percent: 70, basis: "관측 최신", source: "dashboard", workId: null},
  ];
  return {
    session: selected,
    agents: {main: {name: selected.name, agentType: "claude", state: "done", toolName: "Agent"}, children: []},
    timeline: [], blockers: [], transcript: false,
    workItems, workSummary: selected.workSummary || {total: 0, completed: 0, inProgress: 0, answered: 0, interrupted: 0},
    progressSeries, historyWarnings: [],
  };
}
function response(payload, status = 200, textPromise = null, jsonPromise = null) {
  const serialized = JSON.stringify(payload);
  return {
    ok: status >= 200 && status < 300,
    status,
    text: () => textPromise || Promise.resolve(serialized),
    json: () => jsonPromise || Promise.resolve(payload),
  };
}

let fetchMode = "normal";
let delayedAResolve = null;
let failCOnce = false;
let cFailures = 0;
globalThis.fetch = async (url) => {
  if (url === "/api/snapshot") return response(snapshotPayload);
  const match = /^\/api\/session\?id=(.*)$/.exec(url);
  if (!match) throw new Error("unexpected fetch " + url);
  const id = decodeURIComponent(match[1]);
  if (fetchMode === "race" && id === "A" && !delayedAResolve) {
    const textPromise = new Promise((resolve) => { delayedAResolve = resolve; });
    return response(detailPayload("A"), 200, textPromise);
  }
  if (id === "C" && failCOnce) {
    failCOnce = false;
    cFailures += 1;
    throw new Error("fixture network failure");
  }
  return response(detailPayload(id));
};
"""


NODE_UI_SCENARIOS = r"""
;(async () => {
  const settle = async () => {
    for (let index = 0; index < 12; index += 1) await Promise.resolve();
  };
  const text = (id) => document.getElementById(id).textContent;
  const descendants = (root) => {
    const result = [];
    const visit = (node) => { result.push(node); for (const child of node.children) visit(child); };
    visit(root);
    return result;
  };
  const ancestor = (node, predicate) => {
    for (let current = node; current; current = current.parentNode) if (predicate(current)) return current;
    return null;
  };
  await settle();

  const initialCards = document.getElementById("cards").children;
  const cardSummary = initialCards[0].textContent.includes("작업 4 · 완료 1")
    && initialCards[0].textContent.includes("진행 중 1")
    && initialCards[0].textContent.includes("중단 1")
    && !initialCards[2].textContent.includes("작업 4 · 완료 1");

  const firstCard = document.getElementById("cards").children[0];
  firstCard.dispatchEvent({type: "click"});
  await settle();
  const cardClick = location.hash === "#session=A" && !detailView.hidden && text("detail-body").includes("세션 A");
  const detailNodes = descendants(document.getElementById("detail-body"));
  const exactTitle = (title) => detailNodes.find((node) => node.textContent === title);
  const latestTitle = exactTitle("현재 진행 중인 최신 작업");
  const historyTitleNodes = ["완료한 이전 작업", "설명으로 끝난 작업", "중단된 작업", "현재 진행 중인 최신 작업"]
    .flatMap((title) => detailNodes.filter((node) => node.textContent === title));
  const historyRows = historyTitleNodes.length === 4;
  const latestExpanded = Boolean(latestTitle)
    && Boolean(ancestor(latestTitle, (node) => node.attributes["aria-current"] === "true"))
    && !ancestor(latestTitle, (node) => node.tagName === "details");
  const pastCollapsed = ["완료한 이전 작업", "설명으로 끝난 작업", "중단된 작업"]
    .every((title) => Boolean(ancestor(exactTitle(title), (node) => node.tagName === "details")));
  const historyLabels = ["✔", "▶", "◦", "✕", "완료", "진행 중", "응답 종료", "중단",
    "private-implement", "private-roadmap", "산정 불가", "Step 1", "Step 7", "서브에이전트", "셸"]
    .every((label) => text("detail-body").includes(label))
    && /\d{1,2}:\d{2}/.test(text("detail-body"));
  const polylines = detailNodes.filter((node) => node.tagName === "polyline");
  const pointTitles = detailNodes.filter((node) => node.tagName === "title");
  const trendSegments = polylines.length === 4
    && pointTitles.some((node) => node.textContent.includes("work 4 Step 7"))
    && pointTitles.some((node) => node.textContent.includes("관측 최신"));

  document.getElementById("back").dispatchEvent({type: "click"});
  await settle();
  const secondCard = document.getElementById("cards").children[1];
  let enterPrevented = false;
  secondCard.dispatchEvent({type: "keydown", key: "Enter", preventDefault() { enterPrevented = true; }});
  await settle();
  const enterKey = enterPrevented && location.hash === "#session=B" && text("detail-body").includes("세션 B");
  const trendInsufficient = text("detail-body").includes("추이 기록 부족");

  document.getElementById("back").dispatchEvent({type: "click"});
  await settle();
  const backToList = location.hash === "" && !listView.hidden && detailView.hidden && document.getElementById("cards").children.length === 3;

  fetchMode = "race";
  document.getElementById("cards").children[0].dispatchEvent({type: "click"});
  await settle();
  location.hash = "#session=B";
  await settle();
  const bRenderedBeforeA = text("detail-body").includes("세션 B");
  delayedAResolve(JSON.stringify(detailPayload("A")));
  await settle();
  const responseRace = bRenderedBeforeA && location.hash === "#session=B" && text("detail-body").includes("세션 B") && !text("detail-body").includes("세션 A");

  fetchMode = "normal";
  location.hash = "#session=C";
  await settle();
  failCOnce = true;
  const firstPoll = scheduledTimers.shift();
  await firstPoll();
  await settle();
  const errorShown = text("banner").includes("fixture network failure");
  const secondPoll = scheduledTimers.shift();
  await secondPoll();
  await settle();
  const retryRecovery = cFailures === 1 && errorShown && !text("banner").includes("fixture network failure") && text("detail-body").includes("세션 C");

  process.stdout.write(JSON.stringify({cardClick, enterKey, backToList, responseRace, retryRecovery,
    cardSummary, historyRows, latestExpanded, pastCollapsed, historyLabels, trendSegments, trendInsufficient}));
})().catch((error) => {
  process.stdout.write(JSON.stringify({harnessError: String(error && error.stack ? error.stack : error)}));
  process.exitCode = 2;
});
"""


def run_node_ui_harness():
    node = shutil.which("node")
    if node is None:
        return None, "node 실행 파일 없음"
    scripts = re.findall(r"<script>(.*?)</script>", dashboard.PAGE_HTML, re.DOTALL)
    if len(scripts) != 1:
        return None, f"PAGE_HTML script 블록 expected=1, actual={len(scripts)}"
    with tempfile.TemporaryDirectory(prefix="orca dashboard node ui ") as temporary_directory:
        harness_path = Path(temporary_directory) / "ui-contract.js"
        harness_path.write_text(
            NODE_UI_HARNESS + "\n" + scripts[0] + "\n" + NODE_UI_SCENARIOS,
            encoding="utf-8",
        )
        try:
            result = subprocess.run(
                [node, str(harness_path)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return None, f"{type(error).__name__}: {error}"
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        return None, (
            f"node JSON 파싱 실패: {error}; exit={result.returncode}; "
            f"stdout={result.stdout!r}; stderr={result.stderr!r}"
        )
    if result.returncode != 0 or payload.get("harnessError"):
        return None, (
            f"node harness 오류: exit={result.returncode}; payload={payload!r}; "
            f"stderr={result.stderr!r}"
        )
    return payload, f"node={node}; payload={payload!r}; stderr={result.stderr!r}"


print("상세 UI Node 동작")
node_ui_result, node_ui_detail = run_node_ui_harness()
for result_key, test_name in (
    ("cardClick", "① 카드 클릭은 #session=<id> 상세로 진입"),
    ("enterKey", "② 카드 Enter 키는 상세로 진입"),
    ("backToList", "③ 뒤로가기는 해시를 비우고 목록 복귀"),
    ("responseRace", "④ A 응답 지연 중 B 이동 시 최종 상세는 B"),
    ("retryRecovery", "⑤ 상세 요청 실패 후 다음 폴링 성공 시 오류 해제"),
):
    check(
        test_name,
        isinstance(node_ui_result, dict) and node_ui_result.get(result_key) is True,
        node_ui_detail,
    )

for result_key, test_name in (
    ("historyRows", "작업 히스토리는 workItems 4개 행을 모두 렌더"),
    ("latestExpanded", "최신 작업은 펼친 행과 aria-current=true 로 표시"),
    ("pastCollapsed", "과거 작업 3개는 details 안에 접어서 표시"),
    ("historyLabels", "작업 행은 결과 4값·pipeline·진행률·Step·도구 수를 표시"),
    ("trendSegments", "진행률 SVG 는 workId·null·dashboard 경계마다 선을 분리"),
    ("trendInsufficient", "유효 진행률 점이 2개 미만이면 추이 기록 부족 표시"),
    ("cardSummary", "카드는 workSummary 요약을 표시하고 None 이면 생략"),
):
    check(
        test_name,
        isinstance(node_ui_result, dict) and node_ui_result.get(result_key) is True,
        node_ui_detail,
    )


def has_history_ui_tokens(html):
    dark_marker = "@media (prefers-color-scheme: dark)"
    if dark_marker not in html:
        return False
    light_css, dark_css = html.split(dark_marker, 1)
    tokens = (
        "--chart-line",
        "--chart-observed",
        "--chart-grid",
        "--work-completed",
        "--work-running",
        "--work-answered",
        "--work-interrupted",
    )
    return all(
        re.search(rf"{re.escape(token)}\s*:", light_css)
        and re.search(rf"{re.escape(token)}\s*:", dark_css)
        for token in tokens
    )


check(
    "작업·차트 신규 토큰은 라이트·다크에 모두 있고 script 1개·innerHTML 데이터 대입 없음",
    has_history_ui_tokens(dashboard.PAGE_HTML)
    and len(re.findall(r"<script>", dashboard.PAGE_HTML)) == 1
    and avoids_data_inner_html(dashboard.PAGE_HTML),
    "missing exact H7 tokens, multiple scripts, or non-empty innerHTML assignment",
)


print("H8 serve 테스트 격리")
with tempfile.TemporaryDirectory(prefix="orca dashboard h8 fixture ") as temporary_directory:
    isolated_environment = fixture_environment(temporary_directory)
    expect_equal(
        "fixture_environment 는 모든 공용 serve 테스트에 임시 history 디렉토리 제공",
        lambda: isolated_environment.get("ORCA_DASHBOARD_HISTORY_DIR"),
        str(Path(temporary_directory) / "history"),
    )


print()
if failures:
    print(f"실패 {len(failures)}건")
    sys.exit(1)
print("전부 통과")
