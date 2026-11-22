#!/bin/bash
# Add a separate native queue; discover USB without a vendor driver dependency.
set -euo pipefail
export LC_ALL=C
QUEUE=QL1100_Native
PPD=/Library/Printers/PPDs/Contents/Resources/Brother-QL1100-Native.ppd.gz
if [ "$#" -gt 1 ]; then echo 'Usage: add-queue.sh [existing-queue | usb-device-URI]' >&2; exit 2; fi
if [ ! -f "$PPD" ]; then echo 'Install the driver package first.' >&2; exit 1; fi
# Query failure must not be mistaken for permission to overwrite a queue.
QUEUES=$(/usr/bin/lpstat -a)
if /usr/bin/printf '%s\n' "$QUEUES" | /usr/bin/grep -q '^QL1100_Native '; then
  echo 'QL1100_Native already exists; refusing to overwrite it.' >&2; exit 1
fi
URI=''
if [ "$#" -eq 1 ]; then
  case "$1" in
    usb://*) URI=$1 ;;
    ''|-*|*[!a-zA-Z0-9_-]*) echo 'Invalid existing queue name.' >&2; exit 2 ;;
    *)
      LINE=$(/usr/bin/lpstat -v "$1")
      PREFIX="device for $1: "
      case "$LINE" in "$PREFIX"*) URI=${LINE#"$PREFIX"};; *) echo 'Cannot read existing queue device.' >&2; exit 1;; esac
      ;;
  esac
else
  DEVICES=$(/usr/sbin/lpinfo -v)
  COUNT=0
  while IFS= read -r LINE; do
    case "$LINE" in
      'direct usb://Brother/QL-1100?'*|'direct usb://Brother/QL-1100c?'*)
        URI=${LINE#direct }; COUNT=$((COUNT + 1)) ;;
    esac
  done <<< "$DEVICES"
  if [ "$COUNT" -ne 1 ]; then
    echo "Found $COUNT matching USB printers. Connect/power on one printer, or pass its exact USB URI from 'lpinfo -v'." >&2
    exit 1
  fi
fi
case "$URI" in
  *$'\n'*|*$'\r'*) echo 'Invalid USB URI.' >&2; exit 2 ;;
  usb://Brother/QL-1100\?*|usb://Brother/QL-1100c\?*) ;;
  *) echo 'Expected a Brother QL-1100 or QL-1100c USB URI.' >&2; exit 2 ;;
esac
if [ "$(id -u)" -eq 0 ]; then
  /usr/sbin/lpadmin -p "$QUEUE" -E -v "$URI" -P "$PPD" -D 'Brother QL-1100 Native ARM64' -o printer-is-shared=false
else
  /usr/bin/sudo /usr/sbin/lpadmin -p "$QUEUE" -E -v "$URI" -P "$PPD" -D 'Brother QL-1100 Native ARM64' -o printer-is-shared=false
fi
echo 'Created QL1100_Native. The default printer is unchanged. No test was printed.'
