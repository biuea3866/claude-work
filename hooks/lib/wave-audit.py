#!/usr/bin/env python3
"""Wave 스폰 감사 — ledger 의 스폰 타임스탬프로 병렬/직렬을 판정한다.

custom-wave-spawn-log.sh 가 적재한 ~/.claude/.wave-ledger/<YYYYMMDD>.jsonl 을 읽어
스폰 간격으로 wave 를 군집화하고, 직렬화 패턴을 탐지해 리포트를 출력한다.

판정 원리:
  - 병렬 스폰: 한 어시스턴트 메시지의 multi-tool-use → 수ms~수초 내 군집.
  - 직렬 스폰: 앞 에이전트 완료를 기다려 다음을 스폰 → 분 단위로 벌어짐.
  → GAP(기본 20초) 이내 연속 스폰 = 같은 wave, 초과 = 새 wave.

사용:
  wave-audit.py [ledger.jsonl] [--gap SECONDS] [--dag tpm-analysis.md]
  인자 없으면 가장 최근 ledger 사용.
"""
import json, os, sys, glob

GAP_DEFAULT = 20.0
LEDGER_DIR = os.path.expanduser("~/.claude/.wave-ledger")


def latest_ledger():
    files = sorted(glob.glob(os.path.join(LEDGER_DIR, "*.jsonl")))
    return files[-1] if files else None


def load(path):
    recs = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    recs.sort(key=lambda r: r.get("ts", 0))
    return recs


def cluster(recs, gap):
    """스폰 간격 > gap 이면 새 wave."""
    waves, cur = [], []
    prev = None
    for r in recs:
        ts = r.get("ts", 0)
        if prev is not None and (ts - prev) > gap:
            waves.append(cur)
            cur = []
        cur.append(r)
        prev = ts
    if cur:
        waves.append(cur)
    return waves


def dag_ideal_widths(dag_path):
    """tpm-analysis.md 'Wave 너비 시뮬레이션' 표에서 이상적 너비 추출 (있으면)."""
    try:
        import re
        text = open(dag_path, encoding="utf-8").read()
    except OSError:
        return None
    widths = []
    in_tbl = False
    for ln in text.splitlines():
        if "Wave 너비 시뮬레이션" in ln:
            in_tbl = True
            continue
        if in_tbl:
            m = re.match(r"\|\s*\d+\s*\|.*\|\s*(\d+)\s*\|", ln)
            if m:
                widths.append(int(m.group(1)))
            elif widths and not ln.strip().startswith("|"):
                break
    return widths or None


def main():
    args = sys.argv[1:]
    gap = GAP_DEFAULT
    dag = None
    ledger = None
    i = 0
    while i < len(args):
        if args[i] == "--gap":
            gap = float(args[i + 1]); i += 2
        elif args[i] == "--dag":
            dag = args[i + 1]; i += 2
        else:
            ledger = args[i]; i += 1
    if not ledger:
        ledger = latest_ledger()
    if not ledger or not os.path.exists(ledger):
        print("ledger 없음 — 아직 서브에이전트 스폰 기록이 없습니다 (또는 로거 미등록).")
        return 0

    recs = load(ledger)
    if not recs:
        print(f"ledger 비어 있음: {ledger}")
        return 0

    waves = cluster(recs, gap)
    widths = [len(w) for w in waves]
    avg = sum(widths) / len(widths)
    size1_runs = max((len([x for x in g]) for g in _runs(widths, 1)), default=0)

    print(f"# Wave 스폰 감사\n")
    print(f"ledger: {ledger}  (스폰 {len(recs)}건, gap={gap}s)")
    print(f"감지된 wave: {len(waves)}개 / 너비 {widths} / 평균 {avg:.1f}\n")
    print("| Wave | 너비 | 스폰 (span) |")
    print("|------|------|------|")
    prev_end = None
    for n, w in enumerate(waves, 1):
        span = w[-1]["ts"] - w[0]["ts"]
        descs = ", ".join((r.get("agent") or r.get("desc") or "?") for r in w)
        print(f"| {n} | {len(w)} | {descs[:60]} (span {span:.1f}s) |")

    ideal = dag_ideal_widths(dag) if dag else None
    verdict = "병렬 양호"
    reasons = []
    if avg < 2 and len(waves) >= 3:
        verdict = "직렬화 의심"
        reasons.append(f"평균 wave 너비 {avg:.1f} < 2, wave {len(waves)}개")
    if size1_runs >= 3:
        verdict = "직렬화 의심"
        reasons.append(f"너비 1 wave 가 {size1_runs}회 연속")
    if ideal:
        idate = sum(ideal) / len(ideal)
        if avg < idate * 0.6:
            verdict = "직렬화 의심"
            reasons.append(f"DAG 이상 평균 너비 {idate:.1f} 대비 실제 {avg:.1f} (60% 미만)")

    print(f"\n## 판정: {verdict}")
    for r in reasons:
        print(f"- {r}")
    if verdict == "직렬화 의심":
        print("\n→ ready 셋을 한 어시스턴트 메시지에 N개 tool_use 로 동시 스폰했는지, "
              "worktree 격리를 썼는지 점검하세요 (commands/implement.md 'Wave 스케줄러 강제 조항').")
    return 0


def _runs(seq, val):
    """연속으로 val 인 구간들을 리스트로."""
    out, cur = [], []
    for x in seq:
        if x == val:
            cur.append(x)
        elif cur:
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    return out


if __name__ == "__main__":
    sys.exit(main())
