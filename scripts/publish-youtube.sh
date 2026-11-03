#!/usr/bin/env bash
# تأیید + آپلود به یوتیوب در یک دستور (OAuth خودت؛ یک‌بار `telton youtube auth`)
#
#   ./scripts/publish-youtube.sh 2026-11-02-sports-longform unlisted "راسول"
#   ./scripts/publish-youtube.sh 2026-11-02-sports-longform public   "راسول"
#   ./scripts/publish-youtube.sh <slug> private "نام" 2026-11-03T18:30:00Z   # زمان‌بندی
#
# بدون آرگومان privacy، پیش‌فرض unlisted است تا اول خودت در یوتیوب چک کنی.

set -euo pipefail
cd "$(dirname "$0")/.."

SLUG="${1:?usage: scripts/publish-youtube.sh <slug> [privacy] [name] [publish-at]}"
PRIVACY="${2:-unlisted}"
NAME="${3:-tooop news}"
PUBLISH_AT="${4:-}"
PY="${PYTHON:-python3}"

echo "== tooop news → youtube ($PRIVACY)"
$PY -m telton publish -p "$SLUG" --by "$NAME"

if [ -n "$PUBLISH_AT" ]; then
  $PY -m telton youtube upload -p "$SLUG" --privacy private --publish-at "$PUBLISH_AT"
else
  $PY -m telton youtube upload -p "$SLUG" --privacy "$PRIVACY"
fi
