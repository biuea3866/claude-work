#!/usr/bin/env python3
"""티켓 wave 배치기 — fanout 자식을 워크트리에 배치하고 실행 순서를 만든다.

`dispatch.py` 는 **노드 DAG** 를 돈다. 이 모듈은 그 위층으로 **티켓 DAG** 를 다룬다.
티켓 N건은 가변 실행 단위 + cwd N개라, 정적 노드 선언으로는 표현할 수 없다.

의존·소유의 정본은 `plan` 노드 산출물이다 (`contracts/design-doc.schema.json` 의
`tickets[].depends_on` · `tickets[].files_touched`). 계약 검증을 통과한 JSON 만 들어온다 —
마크다운 헤더를 파싱하지 않는다.

**같은 wave 의 소유 경로 교집합은 실행 전에 막는다.** 병렬 실행이 곧 머지 충돌이다
(rules/private-ticket.md "Single Writer per File"). design.review 가 설계 시점에 한 번
검사하지만, 리뷰 지적으로 파일이 늘어나면 그 검사는 이미 지났다 — 실행 직전에 다시 본다.

이식 원본: gitkraken-clone-app/.agent/orchestration/runner/wave-graph.py
"""
from __future__ import annotations

import os
import shlex
import subprocess


class WaveError(Exception):
    """티켓 DAG·워크트리 오류. 실행 전에 던진다."""


def fail(message: str):
    raise WaveError(message)


# ---------------------------------------------------------------- 티켓 DAG


def plan_waves(tickets: dict[str, dict]) -> tuple[list[list[str]], list[str]]:
    """대상 집합 안에서만 위상정렬한다.

    대상 밖 의존은 **이미 완료된 것으로 간주**한다 (부분 실행 허용). 무엇을 그렇게 봤는지
    돌려주어 호출부가 출력하게 한다 — 조용히 무시하면 순서가 틀렸는지 알 수 없다.
    """
    external: list[str] = []
    pending = {tid: {d for d in (info.get("depends_on") or []) if d in tickets}
               for tid, info in tickets.items()}
    for tid, info in tickets.items():
        for dep in info.get("depends_on") or []:
            if dep not in tickets:
                external.append(f"{tid} → {dep}")

    waves: list[list[str]] = []
    while pending:
        ready = sorted(t for t, deps in pending.items() if not deps)
        if not ready:
            fail("티켓 의존에 순환이 있습니다 (남은 티켓): "
                 + ", ".join(f"{t}←{sorted(d)}" for t, d in sorted(pending.items())))
        waves.append(ready)
        for tid in ready:
            del pending[tid]
        for deps in pending.values():
            deps -= set(ready)
    return waves, sorted(set(external))


def check_overlap(wave: list[str], tickets: dict[str, dict]) -> list[str]:
    """같은 wave 안의 소유 경로 교집합을 찾는다 (한 파일 = 한 티켓)."""
    conflicts = []
    for index, left in enumerate(wave):
        for right in wave[index + 1:]:
            shared = (set(tickets[left].get("files_touched") or [])
                      & set(tickets[right].get("files_touched") or []))
            if shared:
                conflicts.append(f"{left} ↔ {right}: {sorted(shared)}")
    return conflicts


def build_plan(tickets: dict[str, dict], worktree_root: str,
               branch_prefix: str = "feat") -> dict:
    """실행 전 계획 — wave 분포 · 충돌 · 워크트리 경로. LLM 호출 0."""
    waves, external = plan_waves(tickets)
    conflicts = [c for wave in waves for c in check_overlap(wave, tickets)]
    widths = [len(wave) for wave in waves]
    return {
        "waves": [{"index": i, "ticket_ids": wave} for i, wave in enumerate(waves, start=1)],
        "widths": widths,
        # 모든 wave 너비가 1~2면 직선형 — 분해 실패다 (rules/private-ticket.md fan-out 게이트).
        "linear": all(width <= 2 for width in widths),
        "max_width": max(widths) if widths else 0,
        "external_dependencies": external,
        "conflicts": conflicts,
        "worktrees": {tid: os.path.join(worktree_root, tid.lower()) for tid in tickets},
        "branch_prefix": branch_prefix,
    }


# ---------------------------------------------------------------- 워크트리


def default_worktree_root(repo_root: str) -> str:
    """`<repo-parent>/<repo>-worktrees` — 기존 개인 레포 관행과 같은 규약."""
    repo_root = os.path.abspath(repo_root).rstrip(os.sep)
    return os.path.join(os.path.dirname(repo_root), f"{os.path.basename(repo_root)}-worktrees")


def ensure_worktree(repo_root: str, ticket: str, root: str, branch_prefix: str,
                    base: str = "origin/main") -> str:
    """티켓 전용 워크트리를 확보한다. 이미 있으면 **재사용**한다.

    `git worktree remove` 는 호출하지 않는다 — 사람의 미커밋 변경을 지울 수 있다
    (rules/00-core-directives.md §5 "메인 worktree는 건드리지 않는다" 와 같은 이유).
    """
    path = os.path.join(root, ticket.lower())
    if os.path.isdir(path):
        return path
    os.makedirs(root, exist_ok=True)
    branch = f"{branch_prefix}/{ticket}"
    subprocess.run(["git", "fetch", "origin"], cwd=repo_root,
                   check=False, capture_output=True)
    existing = subprocess.run(["git", "rev-parse", "--verify", branch],
                              cwd=repo_root, capture_output=True)
    if existing.returncode != 0:
        # base 가 없으면 조용히 다른 ref 로 떨어지지 않는다 — 기준 브랜치가 바뀌면
        # 티켓이 엉뚱한 커밋 위에 얹힌다 (rules/private-branch-convention.md).
        if subprocess.run(["git", "rev-parse", "--verify", base],
                          cwd=repo_root, capture_output=True).returncode != 0:
            fail(f"{ticket}: 기준 ref '{base}' 를 찾을 수 없습니다 — "
                 f"`git fetch origin` 을 먼저 돌리거나 --base 로 지정하세요.")
    command = (["git", "worktree", "add", path, branch] if existing.returncode == 0
               else ["git", "worktree", "add", path, "-b", branch, base])
    done = subprocess.run(command, cwd=repo_root, capture_output=True, text=True)
    if done.returncode != 0:
        fail(f"{ticket}: 워크트리 생성 실패 — {shlex.join(command)}\n"
             f"{done.stdout}\n{done.stderr}")
    return path


def ensure_wave_worktrees(repo_root: str, wave: list[str], root: str,
                          branch_prefix: str, base: str = "origin/main") -> dict[str, str]:
    """wave 전원의 워크트리를 **순차로** 확보한다.

    `git worktree add` 는 동시 실행에 안전하지 않다 (같은 인덱스·refs 를 만진다).
    스폰 전에 순차로 만들고, 실행만 병렬로 간다.
    """
    return {ticket: ensure_worktree(repo_root, ticket, root, branch_prefix, base)
            for ticket in wave}
