#!/bin/bash
set -euo pipefail
umask 022
ROOT=$(cd "$(dirname "$0")/.." && pwd -P)
VERSION=$(cat "$ROOT/VERSION")
if [ "$(id -u)" -eq 0 ]; then
  echo 'Build packages as your regular user, not root.' >&2
  exit 1
fi
if [ "$#" -gt 1 ] || { [ "$#" -eq 1 ] && [ "$1" != --stage-only ]; }; then
  echo 'Usage: package.sh [--stage-only]' >&2
  exit 2
fi
make -C "$ROOT" all
/usr/bin/lipo -verify_arch arm64 "$ROOT/build/rastertoql1100"
/usr/bin/codesign --verify "$ROOT/build/rastertoql1100"
STAGE=$(mktemp -d "$ROOT/build/package-stage.XXXXXX")
cleanup() { /bin/rm -rf "$STAGE"; }
trap cleanup EXIT
/bin/mkdir -p "$STAGE/Library/Printers/QL1100Native" "$STAGE/Library/Printers/PPDs/Contents/Resources"
/usr/bin/find "$STAGE/Library" -type d -exec /bin/chmod 755 {} +
/usr/bin/install -m 755 "$ROOT/build/rastertoql1100" "$STAGE/Library/Printers/QL1100Native/rastertoql1100"
/usr/bin/gzip -n -c "$ROOT/ppd/Brother-QL1100-Native.ppd" > "$STAGE/Library/Printers/PPDs/Contents/Resources/Brother-QL1100-Native.ppd.gz"
/bin/chmod 644 "$STAGE/Library/Printers/PPDs/Contents/Resources/Brother-QL1100-Native.ppd.gz"
if [ "${1:-}" = --stage-only ]; then
  trap - EXIT
  echo "$STAGE"
  exit 0
fi
/bin/mkdir -p "$STAGE/installer-scripts"
/usr/bin/install -m 755 "$ROOT/scripts/pkg-preinstall" "$STAGE/installer-scripts/preinstall"
/usr/bin/pkgbuild --root "$STAGE/Library" --install-location /Library --scripts "$STAGE/installer-scripts" --identifier io.github.yuxhuang.brother-ql1100 --version "$VERSION" --ownership recommended "$ROOT/build/QL1100Native-$VERSION.pkg"
/usr/bin/shasum -a 256 "$ROOT/build/QL1100Native-$VERSION.pkg"
