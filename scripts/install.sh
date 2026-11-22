#!/bin/bash
# Install only the two packaged driver files. Queue creation is separate.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd -P)
VERSION=$(cat "$ROOT/VERSION")
PKG="$ROOT/build/QL1100Native-$VERSION.pkg"
if [ "$#" -ne 0 ]; then echo 'Usage: install.sh' >&2; exit 2; fi
if [ ! -f "$PKG" ] || [ -L "$PKG" ]; then
  echo 'Build the package first with scripts/package.sh.' >&2; exit 1
fi
/bin/bash "$ROOT/scripts/pkg-preinstall"
if [ "$(id -u)" -eq 0 ]; then
  /usr/sbin/installer -pkg "$PKG" -target /
else
  /usr/bin/sudo /usr/sbin/installer -pkg "$PKG" -target /
fi
echo 'Driver files installed. Create the separate queue with scripts/add-queue.sh.'
