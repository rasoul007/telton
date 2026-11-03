#!/bin/bash
# مک: روی همین فایل دابل‌کلیک کن
cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  echo "پایتون نصب نیست. از python.org نسخه‌ی 3.11 یا بالاتر را نصب کن."
  read -r -p "Enter…" _
  exit 1
fi

python3 scripts/launcher.py
echo
read -r -p "برای بستن Enter بزن…" _
