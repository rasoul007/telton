# tooop news — ایجنت خبر ورزشی (ساخت ویدیو از صفر تا انتشار)

یک خط فرمان که خبرها را جمع می‌کند، کلیپ‌های گل را از کانال‌های عمومی تلگرام می‌آورد،
اسکریپت فارسی می‌نویسد، نریشن می‌سازد، ویدیوی **۱۹۲۰×۱۰۸۰ (یوتیوب بلند)** رندر می‌کند،
**صفحه‌ی بازبینی** می‌دهد و **بدون تأیید تو هیچ‌چیز را منتشر نمی‌کند**.

```
collect → broll → build → voice → render → review → publish --by "اسم تو"
 تیترها    کلیپ گل   اسکریپت  نریشن   ویدیو    بازبینی    یک دستور
```

## نصب

```bash
pip install -r requirements.txt        # pillow, arabic-reshaper, imageio-ffmpeg, edge-tts, ...
python -m telton --help                # یا: pip install -e . && telton --help
```

نیازی به نصب دستی ffmpeg نیست؛ باینری از `imageio-ffmpeg` استفاده می‌شود.
فونت فارسی (`Vazirmatn`) در `assets/fonts/` هست.

## اجرای کامل یک قسمت ۵ دقیقه‌ای (یوتیوب بلند)

```bash
SLUG=2026-11-02-sports-longform

# ۱) تیترها از RSS
python -m telton collect -p $SLUG

# ۲) کلیپ‌های گل/صحنه از کانال عمومی تلگرام (مثلاً ورزش۳)
python -m telton broll   -p $SLUG --channel varzesh3 --limit 150 --max-clips 6
python -m telton broll   -p $SLUG --list        # فقط فهرست پیام‌های دارای ویدیو

# ۳) stories.json را در فارسی بنویس (با منبع و verified:true)

# ۴) اسکریپت + زیرنویس + کپشن (هدف ۳۰۰ ثانیه)
python -m telton build   -p $SLUG -d 300

# ۵) نریشن فارسی + میکس صدا
python -m telton voice   -p $SLUG -d 300 --rate +10%

# ۶) رندر ۱۹۲۰×۱۰۸۰ (برای شورت: --width 1080 --height 1920)
python -m telton render  -p $SLUG

# ۷) بازبینی → projects/$SLUG/out/review.html

# ۸) تأیید + پکیج انتشار در یک دستور
python -m telton publish -p $SLUG --by "اسم تو"
```

میان‌بر: `python -m telton run -p <slug> -d 300` مراحل ۴ تا ۷ را یک‌جا انجام می‌دهد.
اجرای روزانه‌ی کامل: `./scripts/daily.sh` (جزئیات در همان فایل و `scripts/cron.example`).

اگر فقط متن/فوتیج خبری را عوض کردی (بدون تغییر نریشن): `python -m telton sync -p $SLUG` تایم‌کدها را دست نمی‌زند.

## دروازه‌ی تأیید (مهم‌ترین بخش)

- `approve` هش SHA-256 فایل ویدیو را ثبت می‌کند. `publish` همان هش را دوباره حساب می‌کند؛
  **اگر حتی یک فریم عوض شده باشد، انتشار متوقف می‌شود** (`NotApproved`).
- خبرهایی که `verified: false` دارند اجازه‌ی تأیید نمی‌دهند (مگر با `--force` که در فایل ثبت می‌شود).
- `publish` هیچ آپلودی انجام نمی‌دهد؛ پوشه‌ی `publish-kit/` می‌سازد:
  `video-9x16.mp4`, `subtitles.srt`, `caption.txt`, `thumbnail.jpg`, `sources.md`, `checklist.md`, `manifest.json`.
  آپلود مستقیم به API هر پلتفرم نیاز به اعتبارنامه‌ی خودت دارد (`--platform youtube --live`).

## ساختار پروژه

```
config/style.yaml      رنگ‌ها، فونت‌ها، fps، سرعت تیکر…
config/sources.yaml    فیدهای RSS + قواعد دسته‌بندی خبر (فوتبال ایران، ورزش ایران، حواشی، اروپا، جهان، بعدی)
projects/<slug>/
  project.yaml         عنوان، intro، outro، کپشن، هشتگ
  stories.json         خبرها (فارسی، منبع‌دار، verified)  ← قلب کار تحریریه
  build/               script.md، subtitles.srt، caption.txt، rundown.json، audio.wav، voice/
  out/                 video.mp4، thumbnail.jpg، review.html، approval.json، publish-kit/
broll/                 فوتیج‌های مجاز خودت (گل‌ها/خلاصه‌ها) — با فیلد "broll" در stories.json وصل می‌شود
telton/                کد: collect, rundown, voice, render, review, publish, cli
tests/                 ۳۳ تست (شامل رندر واقعی و دروازه‌ی تأیید)
```

## فوتیج واقعی (گل‌ها و صحنه‌ها)

کلیپ‌های مجاز را در `broll/` بگذار و اسمش را در خبر بنویس:

```json
{ "id": "arsenal-anfield", "broll": "arsenal-liverpool-havertz.mp4" }
```

اگر کلیپی نباشد، به‌جایش «کارت خبری» با تیتر/فکت/منبع ساخته می‌شود؛ ویدیو باز هم کامل و قابل انتشار است.

## نکات مهم

- **اگر محتوا کم باشد** ویدیو کوتاه‌تر از هدف می‌شود (به‌جای پر کردن با سکوت). برای ۵ دقیقه حدود ۱۲–۱۶ خبر لازم است.
- **اگر طولانی شود** `voice --duration` خودش کم‌اهمیت‌ترین خبر‌ها را حذف می‌کند (`--no-fit` خلافش).
- منابع فارسی (ورزش۳، ایرنا…) از بعضی شبکه‌ها بسته‌اند؛ در `config/sources.yaml` با `enabled: false` هستند.
  از شبکه‌ی خودت فعالشان کن یا خبرها را در `stories.json` دستی وارد کن.
- تمام خبرها باید منبع داشته باشند؛ `publish-kit/sources.md` برای کردیت و پاسخ به کامنت «منبع؟» است.

## تست

```bash
python -m pytest tests -q      # 33 passed
```
