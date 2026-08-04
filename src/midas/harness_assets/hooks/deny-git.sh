#!/usr/bin/env bash
# Block git push for the Cursor agent (user-level hook).
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/git-push-policy.sh"

input=$(cat)
command=$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('command',''))" <<<"$input")

if is_git_push_command "$command"; then
  cat <<'EOF'
{"permission":"deny","user_message":"git push is disabled for the agent. Push to remote yourself if needed.","agent_message":"git push is blocked by user hook policy. Do not retry git push."}
EOF
  exit 0
fi

echo '{"permission":"allow"}'
