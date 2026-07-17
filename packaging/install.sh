#!/usr/bin/env bash
# User-space installer for midas (no sudo). Ubuntu 24.04+.
# Prefers the newest pyenv Python (>= 3.11) when available, else system python3.
# Usage: packaging/install.sh   (run from a checkout; or ship next to dist/wheels)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${MIDAS_PREFIX:-$HOME/.local}"
VENV="$PREFIX/share/midas/venv"
BIN="$PREFIX/bin"

# --- dependency checks ------------------------------------------------------
missing=""
for dep in git jq curl ssh; do
    command -v "$dep" >/dev/null 2>&1 || missing="$missing $dep"
done
if [ -n "$missing" ]; then
    echo "error: missing required tools:$missing" >&2
    echo "install them with: sudo apt install git jq curl openssh-client" >&2
    exit 1
fi
command -v docker >/dev/null 2>&1 || \
    echo "warning: docker not found - 'midas test' (Playwright runner) will not work"

# --- pick a Python ------------------------------------------------------------
PY=""
if [ -d "${PYENV_ROOT:-$HOME/.pyenv}/versions" ]; then
    newest="$(ls "${PYENV_ROOT:-$HOME/.pyenv}/versions" 2>/dev/null | sort -V | tail -1 || true)"
    if [ -n "$newest" ] && [ -x "${PYENV_ROOT:-$HOME/.pyenv}/versions/$newest/bin/python3" ]; then
        PY="${PYENV_ROOT:-$HOME/.pyenv}/versions/$newest/bin/python3"
    fi
fi
[ -z "$PY" ] && PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
    echo "error: no python3 found (need >= 3.11)" >&2
    exit 1
fi
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
    echo "error: $PY is older than 3.11" >&2
    exit 1
fi
echo "==> using Python: $PY ($("$PY" --version 2>&1))"

# --- install -------------------------------------------------------------------
echo "==> creating venv at $VENV"
"$PY" -m venv --clear "$VENV"
if compgen -G "$ROOT/dist/wheels/*.whl" >/dev/null; then
    echo "==> installing from bundled wheels"
    "$VENV/bin/pip" install --quiet --no-index --find-links "$ROOT/dist/wheels" midas
else
    echo "==> installing from source (downloads deps from PyPI)"
    "$VENV/bin/pip" install --quiet "$ROOT"
fi

mkdir -p "$BIN"
ln -sf "$VENV/bin/midas" "$BIN/midas"

# --- integrity manifest ----------------------------------------------------------
PKG_DIR="$("$VENV/bin/python" -c 'import midas, os; print(os.path.dirname(midas.__file__))')"
( cd "$PKG_DIR" && find . -type f ! -name MANIFEST.sha256 ! -path '*/__pycache__/*' \
    -exec sha256sum {} + | sed 's| \./|  |' > MANIFEST.sha256 )

echo ""
echo "midas installed to $BIN/midas"
case ":$PATH:" in
    *":$BIN:"*) ;;
    *) echo "note: $BIN is not on your PATH - add it to your shell profile" ;;
esac
echo "Next steps:"
echo "  midas setup     # create the configuration"
echo "  midas doctor    # verify all preflight checks"
echo "  midas enable    # install the cron polling job"
