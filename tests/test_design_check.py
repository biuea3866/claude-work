#!/usr/bin/env python3
"""/private-design 결정적 검사기 테스트 — 대비(WCAG)·모드 누락·색 하드코딩.

실행: python3 tests/test_design_check.py
표준 라이브러리만 사용한다.
"""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills/private-design/scripts/design_check.py")


def load_module(path, name):
    spec = importlib.util.spec_from_loader(
        name, importlib.machinery.SourceFileLoader(name, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


d = load_module(SCRIPT, "design_check")

failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        failures.append(name)
        print(f"  FAIL {name}" + (f" — {detail}" if detail else ""))


def kinds(findings):
    return sorted(f["kind"] for f in findings)


def run_cli(*args):
    proc = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


print("── 대비 계산 ──")

check("흑백 대비는 21:1", round(d.contrast_ratio("#000000", "#FFFFFF"), 1) == 21.0)
check("같은 색 대비는 1:1", round(d.contrast_ratio("#3182F6", "#3182F6"), 2) == 1.0)
check("인자 순서와 무관", d.contrast_ratio("#191F28", "#FFFFFF") == d.contrast_ratio("#FFFFFF", "#191F28"))
check("3자리 hex 를 6자리와 같게 해석", d.contrast_ratio("#fff", "#000") == d.contrast_ratio("#ffffff", "#000000"))
check("#777 on #fff 는 4.48 (AA 경계 바로 아래)",
      round(d.contrast_ratio("#777777", "#FFFFFF"), 2) == 4.48,
      f"{d.contrast_ratio('#777777', '#FFFFFF'):.3f}")

print("── 토큰 검사 ──")

GOOD = {
    "light": {"background": "#FFFFFF", "surface": "#F2F4F6", "text-primary": "#191F28",
              "text-secondary": "#4E5968", "accent": "#3182F6"},
    "dark": {"background": "#17171C", "surface": "#202027", "text-primary": "#FFFFFF",
             "text-secondary": "#B0B8C1", "accent": "#3182F6"},
}
check("기준을 만족하는 토큰은 발견 0건", d.check_tokens(GOOD) == [], str(d.check_tokens(GOOD)))

dark_missing = json.loads(json.dumps(GOOD))
del dark_missing["dark"]["accent"]
found = d.check_tokens(dark_missing)
check("다크에만 빠진 토큰은 missing_mode", kinds(found) == ["missing_mode"], str(found))
check("missing_mode 는 모드·토큰명을 담는다",
      found and found[0]["mode"] == "dark" and found[0]["token"] == "accent", str(found))

no_dark = {"light": GOOD["light"]}
check("dark 블록 자체가 없으면 missing_mode",
      "missing_mode" in kinds(d.check_tokens(no_dark)), str(d.check_tokens(no_dark)))

low = json.loads(json.dumps(GOOD))
low["dark"]["text-secondary"] = "#3A3A40"
found = d.check_tokens(low)
check("다크 보조 글자 대비 부족은 low_contrast", "low_contrast" in kinds(found), str(found))
lc = [f for f in found if f["kind"] == "low_contrast"]
check("low_contrast 는 쉬운 말 메시지에 대비값·기준을 담는다",
      lc and "4.5" in lc[0]["message"] and "다크" in lc[0]["message"], str(lc))

custom = json.loads(json.dumps(GOOD))
custom["pairs"] = [{"fg": "accent", "bg": "background", "min": 3}]
found = d.check_tokens(custom)
check("pairs 로 지정한 쌍을 지정 기준(3:1)으로 검사 — 라이트 accent 4.0 통과",
      not any(f.get("fg") == "accent" and f["mode"] == "light" for f in found), str(found))

strict = json.loads(json.dumps(GOOD))
strict["pairs"] = [{"fg": "accent", "bg": "background", "min": 7}]
found = d.check_tokens(strict)
check("pairs 기준(7:1) 미달은 low_contrast",
      any(f["kind"] == "low_contrast" and f.get("fg") == "accent" for f in found), str(found))

bad_value = json.loads(json.dumps(GOOD))
bad_value["light"]["accent"] = "blue"
check("hex 가 아닌 값은 invalid_color",
      "invalid_color" in kinds(d.check_tokens(bad_value)), str(d.check_tokens(bad_value)))

partial = {"light": {"background": "#FFFFFF", "accent": "#3182F6"},
           "dark": {"background": "#000000", "accent": "#3182F6"}}
check("기본 쌍의 토큰이 없으면 그 쌍은 건너뛴다", d.check_tokens(partial) == [],
      str(d.check_tokens(partial)))

print("── 색 하드코딩 검사 ──")

src = "\n".join([
    "export const Card = () => (",
    "  <div style={{ color: '#fff' }} className=\"bg-blue-500 p-4\">",
    "    <span className=\"text-text-primary\">ok</span>",
    "    <p style={{ background: 'rgba(0,0,0,0.5)' }} />",
    "  </div>",
    ")",
])
found = d.scan_source(src, "src/Card.tsx")
lines = sorted(f["line"] for f in found)
check("hex·Tailwind 원색·rgba 를 각각 잡는다 (2·2·4행)", lines == [2, 2, 4], str(found))
check("시맨틱 토큰 클래스(text-text-primary)는 잡지 않는다",
      not any(f["line"] == 3 for f in found))

css = ":root {\n  --background: #FFFFFF;\n}\n.btn { color: #333; }\n"
found = d.scan_source(css, "src/app.css")
check("CSS 변수 정의 행은 허용, 일반 규칙의 hex 는 잡는다",
      [f["line"] for f in found] == [4], str(found))

check("theme/ 디렉토리의 토큰 정의 파일은 검사하지 않는다",
      d.scan_source("export const light = { background: '#FFFFFF' }", "src/theme/tokens.ts") == [])

check("HTML 엔티티(&#123;)·URL 앵커(#section)는 색으로 보지 않는다",
      d.scan_source("<a href=\"#section\">&#123;</a>", "src/a.tsx") == [],
      str(d.scan_source("<a href=\"#section\">&#123;</a>", "src/a.tsx")))

print("── CLI ──")

with tempfile.TemporaryDirectory() as tmp:
    good_path = os.path.join(tmp, "tokens.json")
    with open(good_path, "w") as f:
        json.dump(GOOD, f)
    code, out = run_cli("tokens", good_path)
    check("tokens: 문제 없으면 exit 0", code == 0, out)

    low_path = os.path.join(tmp, "low.json")
    with open(low_path, "w") as f:
        json.dump(low, f)
    code, out = run_cli("tokens", low_path)
    check("tokens: 발견 있으면 exit 1 + 메시지 출력", code == 1 and "4.5" in out, out)

    src_dir = os.path.join(tmp, "app", "src")
    os.makedirs(os.path.join(src_dir, "theme"))
    os.makedirs(os.path.join(tmp, "app", "node_modules", "lib"))
    with open(os.path.join(src_dir, "Card.tsx"), "w") as f:
        f.write("const a = '#fff'\n")
    with open(os.path.join(src_dir, "theme", "tokens.ts"), "w") as f:
        f.write("const b = '#000'\n")
    with open(os.path.join(tmp, "app", "node_modules", "lib", "x.js"), "w") as f:
        f.write("const c = '#123456'\n")
    code, out = run_cli("source", os.path.join(tmp, "app"))
    check("source: 디렉토리를 순회해 Card.tsx 만 잡는다 (theme·node_modules 제외)",
          code == 1 and "Card.tsx" in out and "tokens.ts" not in out and "x.js" not in out, out)

    code, out = run_cli("--json", "tokens", low_path)
    try:
        parsed = json.loads(out)
        check("--json: JSON 배열을 출력한다", isinstance(parsed, list) and parsed, out)
    except json.JSONDecodeError:
        check("--json: JSON 배열을 출력한다", False, out)

    code, out = run_cli("unknown")
    check("알 수 없는 하위 명령은 exit 2", code == 2, out)

print()
if failures:
    print(f"실패 {len(failures)}건")
    sys.exit(1)
print("전부 통과")
