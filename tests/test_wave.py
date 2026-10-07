#!/usr/bin/env python3
"""티켓 wave 배치기 테스트 — 위상정렬 · Single Writer · 워크트리 확보.

실행: python3 tests/test_wave.py
표준 라이브러리만 사용한다. 실제 git 저장소를 임시로 만들어 워크트리를 검증한다.
"""
import importlib.machinery
import importlib.util
import os
import subprocess
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


w = load_module("orchestration/runner/wave.py", "harness_wave")

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
    except w.WaveError as e:
        check(name, needle in str(e), f"메시지에 '{needle}' 없음: {e}")
        return
    except Exception as e:  # noqa: BLE001
        check(name, False, f"WaveError 가 아닌 예외: {type(e).__name__}: {e}")
        return
    check(name, False, "예외가 나지 않았다")


def T(tid, depends=(), owns=(), role="implement.be"):
    return {"id": tid, "depends_on": list(depends), "files_touched": list(owns), "role": role}


print("── 위상정렬 ──")

tickets = {t["id"]: t for t in [
    T("BE-01"), T("DB-01", role="implement.mysql"),
    T("BE-02", depends=["BE-01"]), T("BE-03", depends=["BE-01"]),
    T("FE-01", depends=["BE-02", "BE-03"], role="implement.fe"),
]}
waves, external = w.plan_waves(tickets)
check("wave 개수", len(waves) == 3, str(waves))
check("wave1 = 의존 없는 티켓", set(waves[0]) == {"BE-01", "DB-01"}, str(waves[0]))
check("wave2 너비 2", set(waves[1]) == {"BE-02", "BE-03"}, str(waves[1]))
check("wave3", waves[2] == ["FE-01"], str(waves[2]))
check("대상 밖 의존 없음", external == [], str(external))

partial = {t["id"]: t for t in [T("BE-02", depends=["BE-01"]), T("BE-03", depends=["BE-01"])]}
waves2, external2 = w.plan_waves(partial)
check("대상 밖 의존은 완료로 간주", len(waves2) == 1 and set(waves2[0]) == {"BE-02", "BE-03"},
      str(waves2))
# 조용히 무시하면 순서가 틀렸는지 알 수 없다 — 무엇을 그렇게 봤는지 돌려준다.
check("대상 밖 의존을 보고", len(external2) == 2 and "BE-01" in external2[0], str(external2))

cyclic = {t["id"]: t for t in [T("A", depends=["B"]), T("B", depends=["A"])]}
expect_fail("순환 의존은 실행 전 중단", lambda: w.plan_waves(cyclic), "순환")

print("── Single Writer per File ──")

overlap = {t["id"]: t for t in [
    T("BE-01", owns=["src/domain/rental/"]),
    T("BE-02", owns=["src/domain/rental/", "src/domain/user/"]),
    T("FE-01", owns=["web/src/pages/"], role="implement.fe"),
]}
conflicts = w.check_overlap(["BE-01", "BE-02", "FE-01"], overlap)
check("교집합 탐지", len(conflicts) == 1 and "rental" in conflicts[0], str(conflicts))
check("교집합 없는 쌍은 통과", "FE-01" not in "".join(conflicts), str(conflicts))
check("단독 wave 는 충돌 없음", w.check_overlap(["BE-01"], overlap) == [])

# 실행 전에 **전 wave** 를 검사한다 — 한 wave 만 보고 시작하면 뒤에서 터진다.
allw = {t["id"]: t for t in [
    T("BE-01", owns=["a/"]), T("BE-02", depends=["BE-01"], owns=["b/"]),
    T("BE-03", depends=["BE-01"], owns=["b/"]),
]}
waves3, _ = w.plan_waves(allw)
found = [c for i, wv in enumerate(waves3) for c in w.check_overlap(wv, allw)]
check("후행 wave 의 교집합도 사전 탐지", len(found) == 1 and "b/" in found[0], str(found))

print("── 워크트리 ──")

with tempfile.TemporaryDirectory() as tmp:
    repo = os.path.join(tmp, "myrepo")
    os.makedirs(repo)
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True, env=env)
    open(os.path.join(repo, "README.md"), "w").write("hi")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True, env=env)

    check("기본 워크트리 루트 규약",
          w.default_worktree_root(repo).endswith("myrepo-worktrees"),
          w.default_worktree_root(repo))

    root = os.path.join(tmp, "wt")
    p1 = w.ensure_worktree(repo, "BE-01", root, "feat", base="main")
    check("워크트리 생성", os.path.isdir(p1) and os.path.isfile(os.path.join(p1, "README.md")), p1)
    check("티켓별 디렉토리", p1.endswith("be-01"), p1)

    branches = subprocess.run(["git", "branch", "--list", "feat/BE-01"], cwd=repo,
                              capture_output=True, text=True, env=env).stdout
    check("브랜치 이름 규약", "feat/BE-01" in branches, branches)

    # 사람의 미커밋 변경을 지울 수 있으므로 remove 를 호출하지 않고 재사용한다.
    open(os.path.join(p1, "WIP.txt"), "w").write("미커밋 작업")
    p2 = w.ensure_worktree(repo, "BE-01", root, "feat", base="main")
    check("기존 워크트리 재사용", p2 == p1)
    check("미커밋 변경 보존", os.path.isfile(os.path.join(p1, "WIP.txt")))

    p3 = w.ensure_worktree(repo, "BE-02", root, "feat", base="main")
    check("서로 다른 티켓은 다른 트리", p3 != p1 and os.path.isdir(p3), p3)

print("── 계획 산출 ──")

plan = w.build_plan(overlap, worktree_root="/tmp/x", branch_prefix="feat")
check("계획에 wave 분포", [len(x["ticket_ids"]) for x in plan["waves"]] == [3], str(plan["waves"]))
check("계획에 충돌 보고", plan["conflicts"] and "rental" in plan["conflicts"][0],
      str(plan["conflicts"]))
check("직선형 DAG 판정", w.build_plan(
    {t["id"]: t for t in [T("A"), T("B", depends=["A"]), T("C", depends=["B"])]},
    worktree_root="/tmp/x", branch_prefix="feat")["linear"] is True)
check("트리형 DAG 판정", plan["linear"] is False, str(plan))

print()
if failures:
    print(f"실패 {len(failures)}건: {failures}")
    sys.exit(1)
print("전부 통과")
