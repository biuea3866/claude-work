#!/usr/bin/env python3
"""벤더 어댑터 — CLI argv 조립 규칙을 TOML 선언에서 읽는다.

**이 파일에는 벤더 이름 분기가 없다.** 새 런타임을 붙이려면 `adapters/<id>.toml` 1개만
추가한다 (adapters/README.md). 어댑터 id 는 `roles.json#runtimes` 의 키와 일치해야 한다 —
`harness lint` 가 대조한다.

이식 원본: gitkraken-clone-app/.agent/orchestration/runner/run-graph.py
다른 점: 노드 키가 `vendor` 가 아니라 **`runtime`** 이다 (roles.json 어휘를 따른다).
"""
from __future__ import annotations

import os
import re
import tomllib

HARNESS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ADAPTER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "adapters")

# 그래프·상태 기계가 소유하는 노드 키. 그 외 키는 어댑터 [flags] 에 있어야 한다.
# 여기 없는 키를 노드가 들면 build_command 가 "지원하지 않습니다" 로 실행 전에 죽는다 —
# 조용히 무시하면 안전 의미(권한·샌드박스)가 사라진 채 돈다.
RESERVED_NODE_KEYS = {
    "id", "runtime", "tier", "role", "skill", "type", "inputs", "needs", "prompt",
    "cwd", "timeout_sec", "requires", "output_contract", "gate", "retry", "on_failure",
    "fanout", "attempts", "degraded", "status", "parent", "children", "ticket",
    # 디스패처가 프롬프트 조립에 쓰는 키 — argv 로 나가지 않는다.
    # 예약어에 없으면 build_command 가 런타임 플래그로 오인해 "지원하지 않습니다" 로 죽는다.
    "agent_file", "upstream", "contract_file",
    # 언더스코어 접두 키(_routing·_note·_gate_note …)는 아래에서 일괄 제외한다.
}


class AdapterError(Exception):
    """어댑터 선언·조립 오류. 실행 전에 던진다."""


def fail(message: str):
    raise AdapterError(message)


def _is_reserved(key: str) -> bool:
    return key in RESERVED_NODE_KEYS or key.startswith("_")


# ---------------------------------------------------------------- 로드


def load_adapters(adapter_dir: str | None = None) -> dict[str, dict]:
    """adapters/*.toml 을 전부 읽어 런타임 레지스트리를 만든다."""
    directory = adapter_dir or ADAPTER_DIR
    adapters: dict[str, dict] = {}
    for name in sorted(os.listdir(directory)) if os.path.isdir(directory) else []:
        if not name.endswith(".toml"):
            continue
        path = os.path.join(directory, name)
        with open(path, "rb") as handle:
            adapter = tomllib.load(handle)
        for key in ("id", "base", "prompt_delivery", "result"):
            if key not in adapter:
                fail(f"{name}: 필수 키 '{key}' 가 없습니다.")
        if adapter["prompt_delivery"] not in ("stdin", "argv"):
            fail(f"{name}: prompt_delivery 는 stdin 또는 argv 여야 합니다.")
        if adapter["result"] not in ("stdout_envelope", "out_file"):
            fail(f"{name}: result 는 stdout_envelope 또는 out_file 여야 합니다.")
        adapters[adapter["id"]] = adapter
    if not adapters:
        fail(f"어댑터가 없습니다 — {directory}")

    # failover 선언 검증 — 존재하지 않는 런타임을 가리키면 실행 전에 실패한다.
    for adapter in adapters.values():
        target = adapter.get("failover", {}).get("fallback_to")
        if target and target not in adapters:
            fail(f"{adapter['id']} 어댑터: failover.fallback_to '{target}' 런타임이 없습니다.")
        if target == adapter["id"]:
            fail(f"{adapter['id']} 어댑터: failover.fallback_to 가 자기 자신입니다.")
    return adapters


# ---------------------------------------------------------------- argv 조립


def render_fragment(template: list[str], value, node_id: str, key: str, root: str) -> list[str]:
    """어댑터의 argv 조각 템플릿에 노드 값을 채운다.

    자리표시자: {value} 원값 · {csv} 리스트를 쉼표로 · {root_path} 하네스 루트 기준 경로(존재 검증)
    """
    rendered: list[str] = []
    for piece in template:
        if "{csv}" in piece:
            if not isinstance(value, list):
                fail(f"노드 '{node_id}': {key} 는 리스트여야 합니다.")
            piece = piece.replace("{csv}", ",".join(str(item) for item in value))
        if "{root_path}" in piece:
            resolved = value if os.path.isabs(str(value)) else os.path.join(root, str(value))
            if not os.path.isfile(resolved):
                fail(f"노드 '{node_id}': {key} 파일 없음 — {resolved}")
            piece = piece.replace("{root_path}", str(resolved))
        if "{value}" in piece:
            piece = piece.replace("{value}", str(value))
        rendered.append(piece)
    return rendered


def build_command(node: dict, adapter: dict, out_path, cwd, root: str | None = None) -> list[str]:
    """어댑터 선언만으로 CLI argv 를 조립한다. 우선순위: 노드 키 > 어댑터 [defaults]."""
    root = root or HARNESS
    flags = adapter.get("flags", {})
    command = list(adapter["base"])

    for key, template in adapter.get("runtime", {}).items():
        slot = {"out_file": out_path, "cwd": cwd}.get(key)
        if slot is None:
            fail(f"{adapter['id']} 어댑터: 알 수 없는 runtime 슬롯 '{key}'")
        command += [piece.replace("{path}", str(slot)) for piece in template]

    values = dict(adapter.get("defaults", {}))
    values.update({k: v for k, v in node.items() if not _is_reserved(k) and v is not None})

    for key, value in values.items():
        if key not in flags:
            fail(
                f"노드 '{node.get('id')}': 런타임 '{adapter['id']}' 는 '{key}' 를 "
                f"지원하지 않습니다 (지원 키: {sorted(flags)})."
            )
        command += render_fragment(flags[key], value, node.get("id", "?"), key, root)
    return command


# ---------------------------------------------------------------- 실행 환경


def build_env(adapter: dict) -> dict:
    """이 런타임으로 넘길 환경 변수. 부모 환경을 복사해 어댑터 `[env]` 선언을 적용한다.

    왜 필요한가: `ANTHROPIC_API_KEY` 가 설정돼 있으면 claude CLI 가 claude.ai 로그인 대신
    그 키를 쓰고, 키에 크레딧이 없으면 **모든 노드가 실패한다** (실측으로 확인).
    코드에 런타임 분기를 두지 않고 어댑터가 선언한다.
    """
    env = dict(os.environ)
    spec = adapter.get("env") or {}
    for name in spec.get("unset") or []:
        env.pop(name, None)
    for name, value in (spec.get("set") or {}).items():
        env[name] = str(value)
    return env


# ---------------------------------------------------------------- 소진 · failover


def detect_exhaustion(adapter: dict, text: str) -> str | None:
    """이 런타임이 소진(usage limit·quota·rate limit)됐다는 신호를 찾는다.

    반환값은 매칭된 패턴이고 없으면 None. 판정은 어댑터 선언에만 의존한다.
    """
    for pattern in adapter.get("failover", {}).get("exhaustion_patterns", []):
        if re.search(pattern, text, re.IGNORECASE):
            return pattern
    return None


def adapt_node_for_failover(node: dict, source: dict, target: dict) -> tuple[dict, list[str]]:
    """노드를 대체 런타임에서 실행 가능한 형태로 바꾼다.

    런타임마다 지원 키가 다르므로(output_schema 는 codex 전용, mcp_config 는 claude 전용)
    그대로 넘기면 build_command 가 실행 전에 죽는다. 여기서 변환·제거하고 **무엇을 버렸는지
    전부 기록한다** — 조용히 사라지면 산출물 품질이 떨어진 이유를 알 수 없다.
    """
    translate = source.get("failover", {}).get("translate", {})
    target_flags = target.get("flags", {})
    adapted = {k: v for k, v in node.items() if _is_reserved(k)}
    adapted["runtime"] = target["id"]
    notes: list[str] = []

    for key, value in node.items():
        if _is_reserved(key) or key == "runtime" or key == "model":
            continue
        rule = translate.get(key, {}).get(str(value))
        if rule:
            adapted[rule["key"]] = rule["value"]
            notes.append(f"{key}={value} → {rule['key']}={rule['value']} (변환)")
        elif key in target_flags:
            adapted[key] = value
        else:
            notes.append(f"{key} 제거 — {target['id']} 미지원")

    fallback_model = source.get("failover", {}).get("fallback_model")
    if fallback_model and "model" in target_flags:
        adapted["model"] = fallback_model
        if node.get("model"):
            notes.append(f"model={node['model']} → {fallback_model}")
    return adapted, notes


# ---------------------------------------------------------------- 접근 등급


def resolve_access(adapter: dict, access: str) -> dict:
    """런타임 중립 접근 등급 → 런타임 네이티브 키.

    `roles.json#roles[].exec.access` 는 read-only·workspace-write·full 만 안다.
    claude 는 permission_mode 로, codex 는 sandbox 로 받는다 — 그 번역표가 어댑터 `[access]` 다.
    코드에 런타임 분기를 두지 않기 위해서다.
    """
    table = adapter.get("access") or {}
    if access not in table:
        fail(f"{adapter['id']} 어댑터: 접근 등급 '{access}' 가 [access] 에 없습니다 "
             f"(선언된 등급: {sorted(table)}).")
    return dict(table[access])


def project_exec(spec: dict, exec_cfg: dict, adapter: dict) -> tuple[dict, list[str]]:
    """role 의 실행 구성을 이 런타임이 받을 수 있는 키로 투영한다.

    런타임마다 지원 키가 다르다 (tools 는 claude 전용). 미지원 키는 제거하되 **무엇을
    버렸는지 기록한다** — 조용히 사라지면 산출물이 왜 달라졌는지 알 수 없다.
    """
    projected = dict(spec)
    notes: list[str] = []
    flags = adapter.get("flags", {})

    for key, value in resolve_access(adapter, (exec_cfg or {}).get("access", "read-only")).items():
        if key in flags:
            projected[key] = value
        else:
            notes.append(f"접근 등급 키 {key} 제거 — {adapter['id']} 미지원")

    for key, value in (exec_cfg or {}).items():
        if key == "access" or key.startswith("_") or value is None:
            continue
        if key in flags:
            projected[key] = value
        else:
            notes.append(f"{key} 제거 — {adapter['id']} 미지원")
    return projected, notes
