#!/usr/bin/env bash
# RTK Cursor preToolUse — absolute PATH so Cursor hook env finds rtk + jq.
export PATH="/home/leanon/.local/bin:/usr/bin:/bin:${PATH:-}"
exec /home/leanon/.local/bin/rtk hook cursor "$@"
