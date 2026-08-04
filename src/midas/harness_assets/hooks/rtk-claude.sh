#!/usr/bin/env bash
# RTK Claude Code PreToolUse — absolute PATH for rtk + jq.
export PATH="/home/leanon/.local/bin:/usr/bin:/bin:${PATH:-}"
exec /home/leanon/.local/bin/rtk hook claude "$@"
