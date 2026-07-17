#!/usr/bin/env bash
# Build the midas .deb (offline-installable: bundles all Python wheels).
# Usage: packaging/deb/build-deb.sh   (from anywhere; needs python3, pip, dpkg-deb)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="$(grep -m1 '^version' "$ROOT/pyproject.toml" | sed 's/.*"\(.*\)"/\1/')"
DIST="$ROOT/dist"
STAGE="$DIST/debstage"
WHEELS="$DIST/wheels"

echo "==> building wheels (midas $VERSION + dependencies)"
rm -rf "$STAGE" "$WHEELS"
mkdir -p "$WHEELS"
python3 -m pip wheel "$ROOT" -w "$WHEELS" --quiet

echo "==> staging package tree"
mkdir -p "$STAGE/DEBIAN" "$STAGE/usr/lib/midas/wheels" "$STAGE/usr/bin"
cp "$WHEELS"/*.whl "$STAGE/usr/lib/midas/wheels/"

cat > "$STAGE/usr/bin/midas" <<'SHIM'
#!/bin/sh
exec /usr/lib/midas/venv/bin/midas "$@"
SHIM
chmod 755 "$STAGE/usr/bin/midas"

cat > "$STAGE/DEBIAN/control" <<CONTROL
Package: midas
Version: $VERSION
Section: devel
Priority: optional
Architecture: all
Depends: python3 (>= 3.11), python3-venv, python3-pip, git, jq, curl, ca-certificates, openssh-client
Recommends: docker.io
Maintainer: Williams Ramos <williams.ramos@99x.io>
Description: Midas - automated Jira-to-commit development pipeline
 Polls Jira for tasks assigned to you, detects project environment
 requirements, clones and branches the repo over ssh, plans and implements
 the solution with headless CLI agents (Claude/Cursor), validates, commits,
 and reports for human validation. Linux only.
CONTROL

cat > "$STAGE/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e
VENV=/usr/lib/midas/venv
echo "midas: creating virtualenv at $VENV"
python3 -m venv --clear "$VENV"
"$VENV/bin/pip" install --quiet --no-index --find-links /usr/lib/midas/wheels midas

# Integrity manifest for the preflight 'corrupted installation' check
PKG_DIR="$("$VENV/bin/python" -c 'import midas, os; print(os.path.dirname(midas.__file__))')"
( cd "$PKG_DIR" && find . -type f ! -name MANIFEST.sha256 ! -path '*/__pycache__/*' \
    -exec sha256sum {} + | sed 's| \./|  |' > MANIFEST.sha256 )

echo ""
echo "midas installed. Next steps (as your normal user, NOT root):"
echo "  midas setup     # create the configuration"
echo "  midas doctor    # verify all preflight checks"
echo "  midas enable    # install the cron polling job"
POSTINST
chmod 755 "$STAGE/DEBIAN/postinst"

cat > "$STAGE/DEBIAN/prerm" <<'PRERM'
#!/bin/sh
set -e
rm -rf /usr/lib/midas/venv
PRERM
chmod 755 "$STAGE/DEBIAN/prerm"

echo "==> building .deb"
mkdir -p "$DIST"
dpkg-deb --build --root-owner-group "$STAGE" "$DIST/midas_${VERSION}_all.deb"
rm -rf "$STAGE"
echo "==> done: $DIST/midas_${VERSION}_all.deb"
