#!/bin/bash
set -euo pipefail
export LC_ALL=C
if [ "$#" -ne 0 ]; then echo 'Usage: sudo scripts/uninstall.sh' >&2; exit 2; fi
if [ "$(id -u)" -ne 0 ]; then echo 'Run this script with sudo to remove the native queue and driver.' >&2; exit 1; fi
for path in /Library /Library/Printers /Library/Printers/QL1100Native /Library/Printers/PPDs /Library/Printers/PPDs/Contents /Library/Printers/PPDs/Contents/Resources /Library/Printers/QL1100Native/rastertoql1100 /Library/Printers/PPDs/Contents/Resources/Brother-QL1100-Native.ppd.gz; do
  if [ -L "$path" ]; then echo "Refusing symlink destination: $path" >&2; exit 1; fi
done
/usr/sbin/pkgutil --pkg-info io.github.yuxhuang.brother-ql1100 >/dev/null
# A failed CUPS query is never evidence that a queue or its jobs are absent.
PRINTERS=$(/usr/bin/lpstat -p)
JOBS=$(/usr/bin/lpstat -o)
for ppd in /etc/cups/ppd/*.ppd; do
  [ -e "$ppd" ] || continue
  if [ -L "$ppd" ]; then echo "Refusing symlink queue PPD: $ppd" >&2; exit 1; fi
  if [ "$ppd" != /etc/cups/ppd/QL1100_Native.ppd ] && /usr/bin/grep -Fq 'QL1100Native/rastertoql1100' "$ppd"; then
    echo "Another queue uses this driver: $ppd. Remove that queue first." >&2; exit 1
  fi
done
if /usr/bin/printf '%s\n' "$PRINTERS" | /usr/bin/grep -q '^printer QL1100_Native '; then
  PPD=/etc/cups/ppd/QL1100_Native.ppd
  if [ ! -f "$PPD" ] || ! /usr/bin/grep -Fq 'QL1100Native/rastertoql1100' "$PPD"; then
    echo 'QL1100_Native does not use this driver; refusing to remove it.' >&2; exit 1
  fi
  if /usr/bin/printf '%s\n' "$JOBS" | /usr/bin/grep -q '^QL1100_Native-[0-9]'; then
    echo 'Native queue has pending jobs. Cancel or finish them before uninstalling.' >&2; exit 1
  fi
  /usr/sbin/lpadmin -x QL1100_Native
fi
/bin/rm -f /Library/Printers/QL1100Native/rastertoql1100 /Library/Printers/PPDs/Contents/Resources/Brother-QL1100-Native.ppd.gz
if [ -d /Library/Printers/QL1100Native ]; then /bin/rmdir /Library/Printers/QL1100Native; fi
if /usr/sbin/pkgutil --pkg-info io.github.yuxhuang.brother-ql1100 >/dev/null 2>&1; then /usr/sbin/pkgutil --forget io.github.yuxhuang.brother-ql1100; fi
echo 'Native driver removed. Other printers and drivers are unchanged.'
