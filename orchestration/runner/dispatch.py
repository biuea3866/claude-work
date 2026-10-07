#!/usr/bin/env python3
"""디스패처 — ready 노드를 실제로 실행한다.

**무엇을 실행할지는 정하지 않는다.** ready 셋은 `bin/harness run` 이 준다. 반대로 상태 기계는
argv 를 모른다 — 그건 `adapter.py` 가 만든다. 두 축을 섞으면 프로파일 전환과 런타임 추가가
서로를 막는다 (ADR 0005).

호출 경로는 `harness run dispatch` 다. 이 파일을 직접 실행하지 않는다.

이식 원본: gitkraken-clone-app/.agent/orchestration/runner/run-graph.py
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import re
import shlex
import subprocess
import sys
import time

# 형제 모듈 import 가 __pycache__ 를 남기지 않게 한다 — 컴파일 산출물은 소스 절대경로를
# 품어서 "머신 절대경로 비의존" rubric 검사를 깨뜨린다 (gitignore 돼도 파일시스템엔 남는다).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_prior_bytecode = sys.dont_write_bytecode
sys.dont_write_bytecode = True
try:
    import adapter as ad  # noqa: E402
finally:
    sys.dont_write_bytecode = _prior_bytecode

DEFAULT_TIMEOUT_SECONDS = 1800


class DispatchError(Exception):
    """실행 전 검증 오류. 노드를 하나도 실행하지 않고 던진다."""


def fail(message: str):
    raise DispatchError(message)


# ---------------------------------------------------------------- 프롬프트 조립


def substitute(text: str, variables: dict, where: str) -> str:
    """{{key}} 를 치환한다. 미해결 자리표시자는 **실행 전에** 실패시킨다.

    남겨두면 노드가 그 문자열을 그대로 요구사항으로 읽는다 — 조용한 오염이다.
    """
    for key, value in (variables or {}).items():
        text = text.replace("{{" + key + "}}", str(value))
    leftover = re.findall(r"\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}", text)
    if leftover:
        fail(f"{where}: 치환되지 않은 자리표시자 {sorted(set(leftover))} — --set 으로 넘기세요.")
    return text


def build_prompt(spec: dict, variables: dict) -> str:
    """노드 프롬프트를 4부로 조립한다: 역할 · 작업 · 입력 · 출력 계약.

    codex 는 서브에이전트 개념이 없어 페르소나를 프롬프트로 주입해야 한다. claude 헤드리스도
    같은 경로를 쓴다 — 런타임마다 다른 조립을 하면 산출물이 런타임에 따라 달라진다.
    """
    sections: list[str] = []
    node_id = spec.get("id", "?")

    agent_file = spec.get("agent_file")
    if agent_file:
        if not os.path.isfile(agent_file):
            fail(f"노드 '{node_id}': 페르소나 파일 없음 — {agent_file}")
        with open(agent_file) as handle:
            sections.append(f"# 역할\n\n{handle.read()}")

    sections.append(
        "# 작업\n\n" + substitute(spec.get("prompt", "").strip(), variables,
                                 f"노드 '{node_id}' prompt"))

    # fanout 자식은 **자기 티켓이 무엇인지** 알아야 한다. 이 섹션이 없으면 자식 전원이
    # 같은 프롬프트를 받아 "배정된 티켓" 을 특정할 수 없다.
    ticket = spec.get("ticket")
    if ticket:
        lines = [f"- **티켓 ID**: `{ticket['id']}`"]
        if ticket.get("title"):
            lines.append(f"- **제목**: {ticket['title']}")
        if ticket.get("path"):
            lines.append(f"- **티켓 문서**: `{ticket['path']}` — 작업 내용의 SSOT. 먼저 읽는다")
        if ticket.get("size"):
            lines.append(f"- **사이즈**: {ticket['size']}")
        if ticket.get("depends_on"):
            lines.append(f"- **선행 티켓**: {', '.join(ticket['depends_on'])} "
                         "— 이미 머지된 것으로 전제한다")
        if ticket.get("files_touched"):
            owned = " · ".join(f"`{path}`" for path in ticket["files_touched"])
            lines.append(f"- **소유 경로**: {owned}")
            lines.append("- **이 경로 밖의 파일은 수정하지 않는다** — 같은 wave 의 다른 "
                         "티켓이 소유한 파일이라 병렬 실행이 곧 머지 충돌이 된다")
        sections.append("# 배정 (이 노드가 담당하는 티켓)\n\n" + "\n".join(lines))

    upstream = spec.get("upstream") or []
    if upstream:
        missing = [path for _, path in upstream if not os.path.isfile(path)]
        if missing:
            # 없는 산출물을 근거로 쓰라고 지시하면 노드가 추측으로 채운다.
            # 산출물은 멀쩡해 보이는데 근거가 빠진 채 만들어진다 — 실행 전에 멈춘다.
            fail(f"노드 '{node_id}': 업스트림 산출물이 없습니다 — {', '.join(missing)}")
        lines = [f"- `{name}` → `{path}`" for name, path in upstream]
        sections.append(
            "# 입력 (선행 노드 산출물)\n\n"
            "아래 파일을 읽어 근거로 사용하세요. 추측하지 마세요.\n\n" + "\n".join(lines))

    contract_file = spec.get("contract_file")
    body = ("최종 응답은 **JSON 객체 하나만** 출력하세요. 산문·코드펜스·설명을 붙이지 마세요.")
    if contract_file and os.path.isfile(contract_file):
        with open(contract_file) as handle:
            body += f"\n\n아래 스키마를 만족해야 합니다.\n\n```json\n{handle.read().strip()}\n```"
    sections.append("# 출력 계약\n\n" + body)
    return "\n\n".join(sections)


def extract_json_object(text: str) -> dict:
    """모델 응답에서 JSON 객체를 추출한다. 코드펜스·머리말·잡음 줄을 허용한다.

    탐욕 정규식(`{.*}`)을 쓰지 않는다 — 실제 CLI 는 봉투 뒤에 경고 줄을 섞어 내보내고,
    그 줄에 중괄호가 있으면 매칭이 봉투 밖까지 삼켜 파싱이 깨진다 (실측으로 확인).
    유효한 객체를 전부 찾아 **가장 큰 것**을 고른다 — 봉투가 잡음보다 크다.
    """
    body = text or ""
    decoder = json.JSONDecoder()
    candidates: list[tuple[int, dict]] = []
    index = 0
    while True:
        start = body.find("{", index)
        if start < 0:
            break
        try:
            value, end = decoder.raw_decode(body, start)
        except json.JSONDecodeError:
            index = start + 1
            continue
        if isinstance(value, dict):
            candidates.append((end - start, value))
        index = end if end > start else start + 1

    if candidates:
        return max(candidates, key=lambda pair: pair[0])[1]
    if "{" not in body:
        return {"_parse_error": "JSON 객체를 찾지 못했습니다.", "_raw": body[:500]}
    return {"_parse_error": "유효한 JSON 객체를 찾지 못했습니다.", "_raw": body[:500]}


# ---------------------------------------------------------------- 실행


def _node_dir(out_dir: str, node_id: str) -> str:
    path = os.path.join(out_dir, node_id.replace("/", "_"))
    os.makedirs(path, exist_ok=True)
    return path


def execute_attempt(spec, adapter, out_dir, prompt, attempt) -> dict:
    """노드를 1회 실행한다. 감지용 원문은 `_scan` 키로 함께 돌려준다 (호출부가 제거)."""
    node_id = spec["id"]
    node_dir = _node_dir(out_dir, node_id)
    out_path = os.path.join(node_dir, "result.json")
    log_path = os.path.join(node_dir, "node.log")
    cwd = spec.get("cwd") or ad.HARNESS
    timeout = spec.get("timeout_sec") or DEFAULT_TIMEOUT_SECONDS
    started = time.monotonic()

    # 이전 시도가 남긴 산출물을 그대로 읽어 성공으로 오판하지 않도록 지운다.
    if os.path.exists(out_path):
        os.unlink(out_path)

    command = ad.build_command(spec, adapter, out_path, cwd)
    env = ad.build_env(adapter)
    stdin_data = ""
    if adapter["prompt_delivery"] == "argv":
        command = command + [prompt]
    else:
        stdin_data = prompt

    def append_log(body: str):
        with open(log_path, "a") as handle:
            handle.write(f"===== attempt {attempt} · runtime={adapter['id']} =====\n{body}")

    base = {"id": node_id, "runtime": adapter["id"], "attempt": attempt,
            "output": out_path, "log": log_path}

    try:
        completed = subprocess.run(command, input=stdin_data, capture_output=True,
                                   text=True, cwd=cwd, timeout=timeout, env=env)
    except FileNotFoundError:
        append_log(f"CLI 없음: {command[0]}\ncommand: {shlex.join(command)}\n")
        return {**base, "status": "failed", "_scan": "",
                "error": f"CLI 를 찾을 수 없습니다: {command[0]}",
                "duration_s": round(time.monotonic() - started, 1)}
    except subprocess.TimeoutExpired:
        append_log(f"TIMEOUT after {timeout}s\ncommand: {shlex.join(command)}\n")
        return {**base, "status": "timeout", "_scan": "",
                "duration_s": round(time.monotonic() - started, 1)}

    duration = round(time.monotonic() - started, 1)
    append_log(f"command: {shlex.join(command)}\n\n--- stdout ---\n{completed.stdout}\n"
               f"--- stderr ---\n{completed.stderr}\n")

    result = {**base, "model": spec.get("model"), "effort": spec.get("effort"),
              "role": spec.get("role"), "exit_code": completed.returncode,
              "duration_s": duration}

    envelope_error = None
    if adapter["result"] == "stdout_envelope":
        envelope = extract_json_object(completed.stdout)
        cost_key = adapter.get("envelope_cost_key")
        if cost_key:
            result["cost_usd"] = envelope.get(cost_key)
        # CLI 가 API 오류(크레딧 부족·인증 실패)에도 **exit 0** 을 내므로 종료 코드만 보면
        # 실패를 성공으로 오판한다. 봉투의 오류 플래그를 명시로 본다.
        error_key = adapter.get("envelope_error_key")
        if error_key and envelope.get(error_key):
            envelope_error = str(envelope.get(
                adapter.get("envelope_result_key", "result")) or "런타임 오류")
        payload = extract_json_object(
            str(envelope.get(adapter.get("envelope_result_key", "result"), "")))
    else:
        # CLI 가 최종 메시지를 파일에 직접 쓴다.
        if os.path.isfile(out_path):
            with open(out_path) as handle:
                payload = extract_json_object(handle.read())
        else:
            payload = {"_parse_error": f"{adapter['id']} 가 출력 파일을 쓰지 않았습니다."}
    with open(out_path, "w") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    ok = (completed.returncode == 0 and "_parse_error" not in payload
          and not envelope_error)
    result["status"] = "ok" if ok else "failed"
    if envelope_error:
        result["error"] = envelope_error
    elif not ok and "_parse_error" in payload:
        result["error"] = payload["_parse_error"]
    result["_scan"] = f"{completed.stdout}\n{completed.stderr}"
    return result


def run_node(spec: dict, adapters: dict, out_dir: str, variables: dict,
             failover: bool = True) -> dict:
    """노드를 실행하고, 런타임 소진이 감지되면 대체 런타임으로 **1회만** 재시도한다.

    hop 을 1회로 제한하는 이유: claude → codex → claude 순환을 막고, 양쪽이 모두 소진된
    상황에서 무한 재시도로 시간을 태우지 않기 위해서다.
    """
    node_id = spec["id"]
    if spec["runtime"] not in adapters:
        fail(f"노드 '{node_id}': 런타임 '{spec['runtime']}' 어댑터가 없습니다 "
             f"(등록: {sorted(adapters)}).")

    prompt = build_prompt(spec, variables)
    node_dir = _node_dir(out_dir, node_id)
    with open(os.path.join(node_dir, "prompt.txt"), "w") as handle:
        handle.write(prompt)
    log_path = os.path.join(node_dir, "node.log")
    if os.path.exists(log_path):
        os.unlink(log_path)

    current = spec
    adapter = adapters[spec["runtime"]]
    tried = [spec["runtime"]]
    history: list[dict] = []

    while True:
        result = execute_attempt(current, adapter, out_dir, prompt, len(tried))
        scan = result.pop("_scan", "")
        if result["status"] == "ok" or not failover:
            break

        target_id = adapter.get("failover", {}).get("fallback_to")
        signal = ad.detect_exhaustion(adapter, scan)
        if not signal or not target_id or target_id in tried:
            break
        # 검증자를 피검증자와 같은 런타임으로 넘기면 교차 리뷰가 무력화된다.
        # 정적 lint 는 설정만 보므로, 전환 시점에 여기서 막는다 (ADR 0005).
        if target_id in (spec.get("_forbidden_runtimes") or []):
            result["failover_blocked"] = (
                f"{target_id} 로 전환하면 교차 검증이 깨집니다 — 피검증자가 이미 그 런타임을 "
                f"사용했습니다 (감지 패턴: {signal})")
            break

        target = adapters[target_id]
        adapted, changes = ad.adapt_node_for_failover(current, adapter, target)
        history.append({"from": adapter["id"], "to": target_id, "signal": signal,
                        "failed_status": result["status"], "changes": changes})
        with open(log_path, "a") as handle:
            handle.write(f"\n===== FAILOVER {adapter['id']} → {target_id} =====\n"
                         f"감지 패턴: {signal}\n"
                         + "".join(f"- {c}\n" for c in changes))
        current, adapter = adapted, target
        tried.append(target_id)

    if history:
        result["failover"] = history
        result["runtime_requested"] = spec["runtime"]
    return result


def run_wave(specs: list[dict], adapters: dict, out_dir: str, variables: dict,
             max_parallel: int = 4, failover: bool = True,
             dry_run: bool = False, on_done=None) -> list[dict]:
    """같은 wave 의 노드를 동시에 실행한다.

    **실행 전에 전 노드의 프롬프트를 조립해 검증한다** — 노드 실행 중 자리표시자 오류로
    실패하면 이미 쓴 비용이 날아간다.
    """
    for spec in specs:
        build_prompt(spec, variables)

    if dry_run:
        return [{"id": s["id"], "runtime": s["runtime"], "model": s.get("model"),
                 "role": s.get("role"), "status": "dry-run"} for s in specs]

    results: list[dict] = []
    workers = max(1, min(max_parallel, len(specs)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run_node, s, adapters, out_dir, variables, failover): s
                   for s in specs}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            if on_done:
                on_done(result)
    return results
