#!/usr/bin/env python3
"""/private-design 결정적 검사기 — LLM 판단 대신 계산으로 판정하는 항목만 둔다.

  design_check.py [--json] tokens <tokens.json>   대비(WCAG AA)·모드 누락·값 형식
  design_check.py [--json] source <path...>       색 하드코딩 (no-hardcoded-color)

exit 0 = 발견 없음 / 1 = 발견 있음 / 2 = 사용법 오류.
메시지는 디자인 용어를 모르는 사용자가 읽는다는 전제로 쉬운 말로 쓴다.

tokens.json 형식:
  {"light": {"background": "#FFFFFF", ...}, "dark": {...},
   "pairs": [{"fg": "accent", "bg": "background", "min": 3}]}   # pairs 는 선택, 기본 쌍에 추가된다
"""
import json
import os
import re
import sys

MODES = ("light", "dark")
MODE_LABEL = {"light": "라이트 모드", "dark": "다크 모드"}

# 본문 글자 기준 WCAG AA 4.5:1. 토큰이 없으면 그 쌍은 건너뛴다.
DEFAULT_PAIRS = [
    {"fg": fg, "bg": bg, "min": 4.5}
    for fg in ("text-primary", "text-secondary")
    for bg in ("background", "surface")
]

HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

SOURCE_EXTS = {".ts", ".tsx", ".js", ".jsx", ".css", ".scss", ".html", ".vue"}
SKIP_DIRS = {"node_modules", "dist", "build", ".git", ".next", "coverage", "theme"}

TAILWIND_PALETTE = ("slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|"
                    "teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose")
TAILWIND_PREFIX = ("bg|text|border|ring|fill|stroke|from|via|to|outline|divide|placeholder|"
                   "decoration|shadow|caret")
HARDCODED_PATTERNS = [
    ("hex", re.compile(r"(?<![&\w])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})\b")),
    ("function", re.compile(r"\b(?:rgba?|hsla?)\(")),
    ("tailwind", re.compile(rf"\b(?:{TAILWIND_PREFIX})-(?:(?:{TAILWIND_PALETTE})-\d{{2,3}}|white|black)\b")),
]
CSS_VARIABLE_DEFINITION = re.compile(r"^\s*--[\w-]+\s*:")


def _channel(value):
    c = value / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(hex_color):
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(color_a, color_b):
    la, lb = sorted((_luminance(color_a), _luminance(color_b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def check_tokens(tokens):
    findings = []
    palettes = {mode: tokens.get(mode) or {} for mode in MODES}

    names = set(palettes["light"]) | set(palettes["dark"])
    for mode in MODES:
        other = MODE_LABEL["dark" if mode == "light" else "light"]
        for name in sorted(names - set(palettes[mode])):
            findings.append({
                "kind": "missing_mode", "mode": mode, "token": name,
                "message": f"{MODE_LABEL[mode]}: '{name}' 색이 정해지지 않았어요. "
                           f"{other}에만 있어서 {MODE_LABEL[mode]}에서는 화면이 깨질 수 있어요.",
            })

    invalid = set()
    for mode in MODES:
        for name, value in sorted(palettes[mode].items()):
            if not isinstance(value, str) or not HEX_RE.match(value):
                invalid.add((mode, name))
                findings.append({
                    "kind": "invalid_color", "mode": mode, "token": name,
                    "message": f"{MODE_LABEL[mode]}: '{name}' 값({value})이 #RRGGBB 형식이 아니라 "
                               f"대비를 계산할 수 없어요.",
                })

    for pair in DEFAULT_PAIRS + list(tokens.get("pairs") or []):
        fg, bg, minimum = pair["fg"], pair["bg"], float(pair.get("min", 4.5))
        for mode in MODES:
            palette = palettes[mode]
            if fg not in palette or bg not in palette:
                continue
            if (mode, fg) in invalid or (mode, bg) in invalid:
                continue
            ratio = contrast_ratio(palette[fg], palette[bg])
            if ratio < minimum:
                findings.append({
                    "kind": "low_contrast", "mode": mode, "fg": fg, "bg": bg,
                    "ratio": round(ratio, 2), "min": minimum,
                    "message": f"{MODE_LABEL[mode]}: '{fg}' 글자가 '{bg}' 배경 위에서 잘 안 보여요 "
                               f"(대비 {ratio:.1f}:1 / 기준 {minimum:g}:1).",
                })
    return findings


def _is_token_definition_file(filename):
    parts = filename.replace("\\", "/").split("/")
    base = parts[-1]
    return ("theme" in parts[:-1] or base.startswith("tokens.")
            or base.startswith("tailwind.config."))


def scan_source(text, filename):
    if _is_token_definition_file(filename):
        return []
    findings = []
    for number, line in enumerate(text.splitlines(), start=1):
        if CSS_VARIABLE_DEFINITION.match(line):
            continue
        for _, pattern in HARDCODED_PATTERNS:
            for match in pattern.finditer(line):
                findings.append({
                    "kind": "hardcoded_color", "file": filename, "line": number,
                    "match": match.group(0),
                    "message": f"{filename}:{number} — 색을 직접 적었어요(`{match.group(0)}`). "
                               f"다크 모드에서 바뀌지 않으니 시맨틱 토큰으로 바꿔야 해요.",
                })
    return findings


def scan_paths(paths):
    findings = []
    for root_path in paths:
        if os.path.isfile(root_path):
            files = [root_path]
        else:
            files = []
            for base, dirs, names in os.walk(root_path):
                dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
                files += [os.path.join(base, n) for n in names
                          if os.path.splitext(n)[1] in SOURCE_EXTS]
        for path in sorted(files):
            with open(path, errors="ignore") as f:
                findings += scan_source(f.read(), path)
    return findings


def main(argv):
    as_json = "--json" in argv
    args = [a for a in argv if a != "--json"]
    if len(args) < 2 or args[0] not in ("tokens", "source"):
        print(__doc__, file=sys.stderr)
        return 2

    if args[0] == "tokens":
        with open(args[1]) as f:
            findings = check_tokens(json.load(f))
    else:
        findings = scan_paths(args[1:])

    if as_json:
        print(json.dumps(findings, ensure_ascii=False, indent=2))
    elif findings:
        for finding in findings:
            print(f"- {finding['message']}")
        print(f"\n발견 {len(findings)}건")
    else:
        print("발견 0건 — 문제 없어요.")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
