#!/usr/bin/env bash
# اجرای روزانه‌ی tooop news — یک دستور، یک قسمت آماده‌ی تأیید.
#
#   ./scripts/daily.sh                     # پروژه‌ی امروز، ۵ دقیقه، ۱۶:۹
#   ./scripts/daily.sh my-slug 420          # اسلاگ و مدت دلخواه
#   VERTICAL=1 ./scripts/daily.sh           # نسخه‌ی عمودی ۹:۱۶ برای ریلز
#
# مرحله‌ها: collect → (اگر stories.json بود) build → voice → render → review
# در پایان فقط این را بزن:  python -m telton publish -p <slug> --by "اسم تو"

set -euo pipefail
cd "$(dirname "$0")/.."

SLUG="${1:-$(date +%Y-%m-%d)-tooop}"
DURATION="${2:-300}"
PY="${PYTHON:-python3}"

echo "== tooop news · $SLUG · ${DURATION}s"

$PY -m telton collect -p "$SLUG" || true

if [ ! -f "projects/$SLUG/stories.json" ]; then
  cat <<EOF

⚠️  هنوز stories.json نداریم.
    تیترهای خام: projects/$SLUG/build/candidates.md
    ۱) خبرها را در فارسی بنویس → projects/$SLUG/stories.json  (verified: true)
    ۲) کلیپ گل‌ها را بگیر:  $PY -m telton broll -p $SLUG --channel varzesh3
    ۳) دوباره همین اسکریپت را بزن.
EOF
  exit 0
fi

# کلیپ‌های واقعی از کانال‌های عمومی تلگرام (اختیاری، با مجوز/کردیت خودت)
$PY -m telton broll -p "$SLUG" --channel varzesh3 --max-clips 6 || true

$PY -m telton build -p "$SLUG" -d "$DURATION"
$PY -m telton voice -p "$SLUG" -d "$DURATION" --rate +10%

if [ "${VERTICAL:-0}" = "1" ]; then
  $PY -m telton render -p "$SLUG" --width 1080 --height 1920
else
  $PY -m telton render -p "$SLUG"          # ۱۶:۹ · ۱۹۲۰×۱۰۸۰ · یوتیوب
fi

$PY -m telton review -p "$SLUG"

echo
echo "آماده‌ی تأیید: projects/$SLUG/out/review.html"
echo "انتشار:        $PY -m telton publish -p $SLUG --by \"اسم تو\""
