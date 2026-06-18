#!/usr/bin/env bash
# PreToolUse hook (Bash matcher) — kubectl/aws/terraform 의 write 동사를 차단.
# readonly 작업(get/describe/logs/top/ls/show 등)은 통과.

set -euo pipefail

input=$(cat)
command=$(printf '%s' "$input" | python3 -c "import json,sys;print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || true)

[[ -z "$command" ]] && exit 0

# 명령을 ; && || | 로 분리해 각 sub-command 의 첫 토큰을 검사 (echo 안의 문자열 등 false positive 회피)
# python으로 안전 파싱 (명령은 환경변수로 전달해 stdin 충돌 회피)
verdict=$(COMMAND="$command" python3 - <<'PY'
import os, re, sys
cmd = os.environ.get("COMMAND", "")
# 단순 분할 — quote 안의 separator 는 분리하지 않음
parts = re.split(r'(?:(?<=[^\\])|^)[;&|]+', cmd)

K8S_WRITE = {"apply","create","delete","patch","edit","replace","rollout","scale","exec","cp","port-forward","drain","cordon","uncordon","taint","label","annotate"}
TF_WRITE = {"apply","destroy","import","taint","untaint"}
# AWS: 동사가 'service action' 형태. write 표시어
AWS_WRITE_PREFIX = ("put-","create-","update-","delete-","attach-","detach-","modify-","rotate-","deploy-","terminate-","stop-","reboot-","cancel-","tag-","untag-","run-","send-","publish-","invoke","import-","restore-","register-","deregister-","enable-","disable-","revoke-","set-","start-","apply-")
AWS_WRITE_EXACT = {"cp","mv","rm","sync","mb","rb"}  # s3 high-level

def collect_positionals(toks):
    """옵션·옵션값 페어를 건너뛰고 positional (non-option) 토큰만 모은다.

    휴리스틱:
      - `--long=value`  → 1 토큰 skip
      - `--long`        → 다음 토큰이 옵션 prefix(-) 가 아니면 옵션 값으로 보고 둘 다 skip.
                          (boolean flag 의 false negative 보다 옵션 값을 verb 로 오인하는
                           false positive 차단이 보안적으로 우선.)
      - `-short`/`-s`   → 같은 휴리스틱 (값-받는 short 가 다수)
    리턴: positional 토큰 리스트.
    """
    out = []
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.startswith('--'):
            if '=' in t:
                i += 1
            elif i + 1 < len(toks) and not toks[i+1].startswith('-'):
                i += 2
            else:
                i += 1
        elif t.startswith('-') and len(t) > 1:
            # terraform 은 `-chdir=DIR`, `-var=K=V`, `-var-file=PATH` 처럼 single-dash + `=` 도 쓴다.
            if '=' in t:
                i += 1
            elif i + 1 < len(toks) and not toks[i+1].startswith('-'):
                i += 2
            else:
                i += 1
        else:
            out.append(t)
            i += 1
    return out

for p in parts:
    toks = p.strip().split()
    if not toks:
        continue
    # 선행 env 변수 할당 (FOO=bar cmd ...) 건너뜀
    i = 0
    while i < len(toks) and re.match(r'^[A-Z_][A-Z0-9_]*=', toks[i]):
        i += 1
    if i >= len(toks):
        continue
    head = toks[i]
    rest = toks[i+1:]
    positionals = collect_positionals(rest)
    if head == "kubectl":
        # write 동사가 옵션 뒤에 올 수 있음 — 첫 positional 토큰을 verb 로 간주.
        if positionals and positionals[0] in K8S_WRITE:
            print(f"KUBECTL:{positionals[0]}")
            sys.exit(0)
    elif head == "terraform":
        if positionals and positionals[0] in TF_WRITE:
            print(f"TERRAFORM:{positionals[0]}")
            sys.exit(0)
    elif head == "aws":
        # aws <service> <action>
        if len(positionals) >= 2:
            service, action = positionals[0], positionals[1]
            if action.startswith(AWS_WRITE_PREFIX) or action in AWS_WRITE_EXACT:
                print(f"AWS:{service} {action}")
                sys.exit(0)
print("OK")
PY
)

if [[ "$verdict" != "OK" ]]; then
  cat >&2 <<EOF
🛑 인프라 write 동사 차단됨.

명령: $command
검출: $verdict

본 워크스페이스 정책: kubectl/aws/terraform 은 READONLY 만 허용합니다.
- 허용 예: kubectl get/describe/logs/top, aws s3 ls, aws ssm get-parameter, terraform plan
- 차단 예: kubectl apply/delete/patch, aws * delete-*/put-*, terraform apply/destroy

운영 변경이 필요하면 사용자가 직접 실행하도록 안내하세요. 훅 우회 금지.
EOF
  exit 2
fi

exit 0
