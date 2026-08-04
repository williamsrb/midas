#!/usr/bin/env bash
# Shared git-push detection used by both Cursor's and Claude Code's deny-git hooks,
# so the two agents can't drift onto different policies.
# Usage: source this file, then call `is_git_push_command "$command"` (0 = match).
#
# Also matches RTK-rewritten and env-prefixed forms, e.g.:
#   rtk git push
#   RTK_DISABLED=1 git push
#   FOO=bar rtk git push origin HEAD

is_git_push_command() {
  local command="$1"

  # Drop leading ENV=value assignments
  while [[ "$command" =~ ^[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]+[[:space:]]+(.*)$ ]]; do
    command="${BASH_REMATCH[1]}"
  done

  # Drop optional rtk wrapper (token-opt shell rewrite)
  if [[ "$command" =~ ^rtk[[:space:]]+(.*)$ ]]; then
    command="${BASH_REMATCH[1]}"
  fi

  [[ "$command" =~ ^git[[:space:]]+push([[:space:]]|$) ]] ||
  [[ "$command" =~ ^git[[:space:]]+-[a-zA-Z]+[[:space:]]+[^[:space:]]+[[:space:]]+push([[:space:]]|$) ]] ||
  [[ "$command" =~ ^git[[:space:]]+-[^[:space:]]+([[:space:]]+-[^[:space:]]+)*[[:space:]]+push([[:space:]]|$) ]]
}
