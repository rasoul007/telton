# Telton — ایجنت خبر ورزشی (ساخت ویدیو از صفر تا انتشار)

یک خط فرمان که خبرها را جمع می‌کند، اسکریپت فارسی می‌نویسد، نریشن می‌سازد، ویدیوی ۹:۱۶ رندر می‌کند،
**صفحه‌ی بازبینی** می‌دهد و **بدون تأیید تو هیچ‌چیز را منتشر نمی‌کند**.

```
collect → build  → voice  → render → review → approve → publish
 تیترها    اسکریپت   نریشن    ویدیو     بازبینی   تأیید تو    پکیج انتشار
```

## نصب

```bash
pip install -r requirements.txt        # pillow, arabic-reshaper, imageio-ffmpeg, edge-tts, ...
python -m telton --help                # یا: pip install -e . && telton --help
```

نیازی به نصب دستی ffmpeg نیست؛ باینری از `imageio-ffmpeg` استفاده می‌شود.
فونت فارسی (`Vazirmatn`) در `assets/fonts/` هست.

## اجرای کامل یک قسمت ۵ دقیقه‌ای

```bash
# ۱) تیترها را از RSS بگیر (BBC/AFC/Google News و هر فید دیگری در config/sources.yaml)
python -m telton collect -p 2026-11-02-sports-longform

# ۲) stories.json را در فارسی بنویس (توسط تو یا Cline) — با منبع و verified:true

# ۳) اسکریپت + زیرنویس + کپشن برای هدف ۳۰۰ ثانیه
python -m telton build -p 2026-11-02-sports-longform -d 300

# ۴) نریشن فارسی + میکس صدا
python -m telton voice -p 2026-11-02-sports-longform -d 300 --rate +10%

# ۵) رندر ویدیو ۱۰۸۰×۱۹۲۰
python -m telton render -p 2026-11-02-sports-longform

# ۶) صفحه‌ی بازبینی را در مرورگر باز کن
#    projects/<slug>/out/review.html

# ۷) تأیید (هش ویدیو ثبت می‌شود)
python -m telton approve -p 2026-11-02-sports-longform --by "نام تو"

# ۸) پکیج انتشار
python -m telton publish -p 2026-11-02-sports-longform
```

میان‌بر: `python -m telton run -p <slug> -d 300` مراحل ۳ تا ۶ را یک‌جا انجام می‌دهد.

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
