#!/usr/bin/env python3
"""티켓 md → plan 산출물 브릿지.

`harness run wave` 는 `plan` 노드의 **계약 검증 통과 JSON** 에서 티켓을 읽는다. 그런데 실제
티켓은 손으로 쓴 md 다 (rules/private-ticket.md — "md 파일이 유일한 티켓이다"). 이 모듈이
그 간극을 메운다: md 를 읽어 contracts/design-doc.schema.json 을 만족하는 결과를 만든다.

**추측하지 않는다.** role 을 접두사만으로 정하지 않고, 소유 경로가 없으면 실패한다 —
Single Writer 검증의 입력이 없는 채로 병렬 실행하면 그게 곧 머지 충돌이다.

파싱 대상:
  <티켓 디렉토리>/<PREFIX>-NN-<슬러그>.md   각 티켓 (`## 의존` 섹션)
  <티켓 디렉토리>/_분해-DAG.md              소유 경로 표 (`| ID | `경로`, ... |`)
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_prior_bytecode = sys.dont_write_bytecode
sys.dont_write_bytecode = True
try:
    import wave as wv  # noqa: E402
finally:
    sys.dont_write_bytecode = _prior_bytecode

TICKET_RE = re.compile(r"^((?:BE|FE|DB|INFRA)-\d+)-.*\.md$")
ID_RE = re.compile(r"(?:BE|FE|DB|INFRA)-\d+")

# 접두사 → role. DB·INFRA 는 1:1 이 아니므로 본문 근거로 갈린다.
DIRECT_ROLE = {"BE": "implement.be", "FE": "implement.fe"}
AMBIGUOUS_ROLE = {
    "DB": [("implement.mysql", ("flyway", "mysql", "mariadb")),
           ("implement.mongodb", ("mongodb", "mongo", "컬렉션"))],
    "INFRA": [("implement.kafka", ("kafka", "토픽", "topic", "consumer", "producer")),
              ("implement.redis", ("redis", "캐시", "ttl", "분산 락"))],
}


class TicketError(Exception):
    """티켓 파싱·정합 오류. plan 을 만들지 않고 던진다."""


def fail(message: str):
    raise TicketError(message)


# ---------------------------------------------------------------- 파싱


def _section(text: str, heading: str) -> str:
    """`## <heading>` 부터 다음 `## ` 까지."""
    match = re.search(rf"^##\s*{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)",
                      text, re.M | re.S)
    return match.group(1) if match else ""


def _title(text: str, ticket_id: str, fallback: str) -> str:
    """`# [ID] 제목` 의 제목부. 없으면 파일 슬러그."""
    match = re.search(rf"^#\s*\[{re.escape(ticket_id)}\]\s*(.+?)\s*$", text, re.M)
    return match.group(1) if match else fallback


def _role(ticket_id: str, text: str) -> str:
    prefix = ticket_id.split("-")[0]
    if prefix in DIRECT_ROLE:
        return DIRECT_ROLE[prefix]
    lowered = text.lower()
    hits = [role for role, keywords in AMBIGUOUS_ROLE[prefix]
            if any(k in lowered for k in keywords)]
    if len(hits) == 1:
        return hits[0]
    # 접두사 추론은 금지다 — DB 는 mysql/mongodb, INFRA 는 kafka/redis 로 갈린다.
    # 근거가 없거나 둘 다 걸리면 사람이 정해야 한다.
    reason = "근거가 없습니다" if not hits else f"근거가 여럿입니다 ({hits})"
    fail(f"{ticket_id}: role 을 판정할 수 없습니다 — {reason}. "
         f"후보 {[r for r, _ in AMBIGUOUS_ROLE[prefix]]} 중 하나를 티켓 본문에 명시하거나 "
         "--role 로 지정하세요.")


def parse_owned(dag_path: str) -> dict[str, list[str]]:
    """분해 DAG md 의 소유 경로 표를 읽는다.

    형식: `| BE-02 | \\`a/x.kt\\`, \\`a/y*\\` |` — 쉼표와 가운뎃점(·) 둘 다 구분자로 쓴다.
    """
    owned: dict[str, list[str]] = {}
    with open(dag_path) as handle:
        for line in handle:
            if not line.lstrip().startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 2:
                continue
            match = re.fullmatch(ID_RE, cells[0])
            if not match:
                continue
            paths = re.findall(r"`([^`]+)`", cells[1])
            if not paths:
                paths = [p.strip() for p in re.split(r"[,·]", cells[1]) if p.strip()]
            if paths:
                owned.setdefault(cells[0], []).extend(paths)
    return owned


def find_dag(tickets_dir: str) -> str | None:
    for name in sorted(os.listdir(tickets_dir)):
        if name.startswith("_") and name.endswith(".md") and "DAG" in name.upper():
            return os.path.join(tickets_dir, name)
    return None


def plan_from_tickets(tickets_dir: str, dag_path: str | None = None,
                      doc_path: str | None = None,
                      roles: dict[str, str] | None = None) -> dict:
    """티켓 디렉토리 → design-doc 계약을 만족하는 plan 결과."""
    if not os.path.isdir(tickets_dir):
        fail(f"티켓 디렉토리가 없습니다: {tickets_dir}")

    dag_path = dag_path or find_dag(tickets_dir)
    owned = parse_owned(dag_path) if dag_path else {}

    tickets: list[dict] = []
    for name in sorted(os.listdir(tickets_dir)):
        match = TICKET_RE.match(name)
        if not match:
            continue
        ticket_id = match.group(1)
        with open(os.path.join(tickets_dir, name)) as handle:
            text = handle.read()
        slug = name[len(ticket_id) + 1:-3].replace("-", " ")
        depends = [d for d in ID_RE.findall(_section(text, "의존")) if d != ticket_id]
        files = owned.get(ticket_id) or []
        if not files:
            # 소유 경로가 없으면 Single Writer 검증의 입력이 없다.
            # 그 상태로 병렬 실행하면 머지 충돌이 곧 발생한다 — 조용히 통과시키지 않는다.
            fail(f"{ticket_id}: 소유 경로를 찾지 못했습니다 "
                 f"({'분해 DAG 없음' if not dag_path else os.path.basename(dag_path) + ' 표에 행 없음'}). "
                 "Single Writer 검증을 할 수 없어 병렬 실행을 시작하지 않습니다.")
        tickets.append({
            "id": ticket_id,
            "role": (roles or {}).get(ticket_id) or _role(ticket_id, text),
            "title": _title(text, ticket_id, slug),
            "depends_on": sorted(set(depends)),
            "files_touched": list(dict.fromkeys(files)),
            # 구현자가 읽어야 하는 티켓 md — 작업 내용의 SSOT 다.
            "path": os.path.join(tickets_dir, name),
        })

    if not tickets:
        fail(f"티켓을 찾지 못했습니다: {tickets_dir}/<BE|FE|DB|INFRA>-NN-*.md")

    by_id = {t["id"]: t for t in tickets}
    for ticket in tickets:
        unknown = [d for d in ticket["depends_on"] if d not in by_id]
        if unknown:
            fail(f"{ticket['id']}: 대상에 없는 티켓을 의존합니다 — {unknown}. "
                 "티켓 파일이 빠졌는지 확인하세요.")

    try:
        waves, _ = wv.plan_waves(by_id)
    except wv.WaveError as error:
        # 호출부가 오류 타입 하나만 알면 되게 감싼다.
        fail(str(error))

    widths = [len(w) for w in waves]
    summary = [
        f"티켓 {len(tickets)}개 · wave {len(waves)}개 · 너비 {widths}",
        f"근거 티켓: {tickets_dir}",
    ]
    if dag_path:
        summary.append(f"소유 경로 출처: {dag_path}")
    if all(w <= 2 for w in widths):
        summary.append("⚠ 모든 wave 너비가 1~2 — 직선형 DAG 는 분해 실패다 "
                       "(rules/private-ticket.md fan-out 게이트)")

    return {
        "doc_path": doc_path or (dag_path or tickets_dir),
        "sections_present": [],
        "tickets": tickets,
        "waves": [{"index": i, "ticket_ids": w} for i, w in enumerate(waves, start=1)],
        "max_wave_width": max(widths),
        "summary_md": "\n".join(f"- {line}" for line in summary),
    }
