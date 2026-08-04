#!/usr/bin/env bash
# Block git push for the Claude Code agent (user-level PreToolUse hook on Bash).
# Mirrors deny-git.sh's policy for Cursor via the shared git-push-policy.sh, but
# speaks Claude Code's hookSpecificOutput/permissionDecision schema instead of
# Cursor's permission/user_message schema.
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/git-push-policy.sh"

input=$(cat)
command=$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" <<<"$input")

if is_git_push_command "$command"; then
  cat <<'EOF'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"git push is disabled for the agent. Push to remote yourself if needed."}}
EOF
  exit 0
fi

echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'
