#!/usr/bin/env python3
"""private-forbidden-patterns.sh 의 검사 본체.

stdin 으로 PreToolUse hook JSON 을 받아 금지 패턴을 검사한다.
위반 발견 시 stderr 안내 + exit 2, 아니면 exit 0.
기준: rules/private-be-code-convention.md · rules/private-fe-convention.md
"""
import json
import re
import sys

data = json.load(sys.stdin)
tool_input = data.get("tool_input", {})
file_path = tool_input.get("file_path") or tool_input.get("path") or ""

# 검사 대상 텍스트: Write=content, Edit=new_string, MultiEdit=edits[].new_string
texts = []
if tool_input.get("content"):
    texts.append(tool_input["content"])
if tool_input.get("new_string"):
    texts.append(tool_input["new_string"])
for edit in tool_input.get("edits", []) or []:
    if edit.get("new_string"):
        texts.append(edit["new_string"])
if not texts:
    sys.exit(0)

# (rule_id, regex, 대체 안내)
KT_RULES = [
    ("no-jpa-query", re.compile(r"@Query\("),
     "QueryDSL CustomImpl 사용 (비관적 락 @Lock+@Query 는 private-allow:no-jpa-query)"),
    ("no-lob", re.compile(r"@Lob\b"), "@Type(JsonStringType::class) + data class"),
    ("no-local-datetime", re.compile(r"\bLocalDateTime\b"), "ZonedDateTime 으로 통일"),
    ("no-instant", re.compile(r"\bjava\.time\.Instant\b|:\s*Instant\b"), "ZonedDateTime 으로 통일"),
    ("no-clock-injection",
     re.compile(r"(val|var)\s+\w*[Cc]lock\s*:\s*Clock\b|\bjava\.time\.Clock\b"),
     "Clock 빈 주입 금지 — 캡슐화 메서드 내부에서 ZonedDateTime.now() 해결"),
    ("no-double-bang", re.compile(r"!!(?![=!])"), "requireNotNull() / ?: / ?.let"),
    ("no-optional-return", re.compile(r"\bOptional<|\bjava\.util\.Optional\b"),
     "Kotlin nullable(T?) 사용 — Optional 반환 금지 (Spring Data 파생 쿼리는 Impl에서 즉시 언랩)"),
    ("no-consumer-record", re.compile(r"ConsumerRecord<\s*String\s*,\s*String\s*>"),
     "DTO 직접 매핑 + JsonDeserializer"),
]
TS_RULES = [
    ("no-any", re.compile(r":\s*any\b|\bas\s+any\b|<any>|\bany\[\]"),
     "unknown + 타입 좁히기 / 제네릭"),
    ("no-hardcoded-color", re.compile(r"['\"]#[0-9a-fA-F]{3,8}['\"]|rgba?\("),
     "시맨틱 테마 토큰 사용 (라이트/다크 모드 의무)"),
]

if re.search(r"\.(kt|kts)$", file_path):
    rules = list(KT_RULES)
    is_kt_test = bool(re.search(r"/src/test/|Test\.kt$|Spec\.kt$", file_path))
    if is_kt_test:
        # 신규 테스트는 Kotest 강제 — JUnit(@RunWith/SpringRunner/org.junit) 금지
        rules.append((
            "no-junit",
            re.compile(r"import\s+org\.junit|@RunWith\b|\bSpringRunner\b"),
            "Kotest(BehaviorSpec/DescribeSpec/FunSpec) 사용 — 신규 테스트에 JUnit 금지",
        ))
    else:
        # 레이어 의존 방향 강제 — 선례(기존 코드)가 위반해도 따르지 않고 컨벤션 우선
        if re.search(r"/domain/", file_path):
            rules.append((
                "no-infra-in-domain",
                re.compile(r"import\s+[\w.]+\.infrastructure\."),
                "domain 레이어는 infrastructure import 금지 — domain interface(Repository/Gateway) 사용",
            ))
        if re.search(r"/application/", file_path):
            rules.append((
                "no-infra-in-application",
                re.compile(r"import\s+[\w.]+\.infrastructure\."),
                "application 레이어는 infrastructure import 금지 — domain interface 사용",
            ))
        if re.search(r"Repository\w*\.kt$", file_path):
            rules.append((
                "no-transactional-in-repository",
                re.compile(r"@Transactional\b"),
                "@Transactional 은 UseCase 에만 선언 — Repository 금지",
            ))
elif re.search(r"\.(ts|tsx|jsx)$", file_path):
    is_test = ".test." in file_path or ".spec." in file_path or "__tests__" in file_path
    # 테스트 파일은 색 규칙 제외 (mock 데이터 등), any 금지는 유지
    rules = [r for r in TS_RULES if r[0] == "no-any"] if is_test else TS_RULES
else:
    sys.exit(0)

violations = []
for text in texts:
    for line in text.splitlines():
        if "private-allow:" in line:
            continue  # 라인 단위 명시적 우회 (감사 대상)
        for rule_id, pattern, guide in rules:
            if pattern.search(line):
                violations.append((rule_id, guide, line.strip()[:100]))

if not violations:
    sys.exit(0)

seen = set()
lines = []
for rule_id, guide, snippet in violations:
    key = (rule_id, snippet)
    if key in seen:
        continue
    seen.add(key)
    lines.append(f"  [{rule_id}] {snippet}\n    → 대체: {guide}")

sys.stderr.write(
    "🛑 [private] 금지 패턴 차단 — 작성하려는 내용이 개인 컨벤션을 위반합니다.\n\n"
    + f"파일: {file_path}\n"
    + "\n".join(lines)
    + "\n\n기준 문서: ~/.claude/rules/private-be-code-convention.md · private-fe-convention.md\n"
    + "정당한 예외라면 해당 라인에 `// private-allow:<rule-id>` 주석을 붙여 재시도하세요 (감사 대상).\n"
)
sys.exit(2)
