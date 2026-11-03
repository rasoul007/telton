# اتصال یوتیوب (آپلود خودکار) — راهنمای یک‌باره

آپلود با **اکانت خودت** انجام می‌شود؛ هیچ کلید یا رمزی به من/کد داده نمی‌شود و توکن در
`.secrets/` می‌ماند (در گیت نادیده گرفته شده).

## ۱) ساخت اعتبارنامه در Google Cloud (۵ دقیقه)

1. برو به <https://console.cloud.google.com/> و یک پروژه‌ی جدید بساز (مثلاً `tooop-news`).
2. **APIs & Services → Library** → جست‌وجو کن **YouTube Data API v3** → **Enable**.
3. **APIs & Services → OAuth consent screen**:
   - User type: **External** → Create
   - App name: `tooop news` · Support email: ایمیل خودت
   - Scopes: لازم نیست دستی اضافه کنی
   - **Test users** → ایمیل همان اکانت گوگلِ کانال را اضافه کن
   - (اختیاری) Publish app تا توکن ۷ روزه منقضی نشود
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: **Desktop app**
   - **Download JSON** → ذخیره کن به‌عنوان:
     ```
     telton/.secrets/client_secret.json
     ```

## ۲) احراز هویت (یک‌بار)

```bash
python -m telton youtube auth
```

مرورگر باز می‌شود → با اکانت کانال **tooop news** وارد شو → دسترسی را تأیید کن.
توکن در `.secrets/youtube-token.json` ذخیره می‌شود و خودکار تمدید می‌شود.

بررسی وضعیت:

```bash
python -m telton youtube status      # نام کانال، تعداد مشترک/ویدیو
```

## ۳) پیش‌نمایش بدون آپلود

```bash
python -m telton youtube upload -p 2026-11-02-sports-longform --dry-run
```

بدنه‌ی دقیق `videos.insert` را چاپ می‌کند: عنوان، توضیحات (با منابع)، تگ‌ها، دسته Sports، زبان fa.

## ۴) انتشار واقعی

```bash
# تا خودت در یوتیوب چک کنی، اول unlisted (پیش‌فرض)
python -m telton youtube upload -p 2026-11-02-sports-longform --privacy unlisted

# انتشار عمومی
python -m telton youtube upload -p 2026-11-02-sports-longform --privacy public

# زمان‌بندی شده (خودکار private + publishAt می‌شود)
python -m telton youtube upload -p 2026-11-02-sports-longform \
  --publish-at 2026-11-03T18:30:00Z
```

در هر آپلود:
- ویدیوی **۱۹۲۰×۱۰۸۰** با نریشن فارسی آپلود می‌شود
- **تامبنیل** (`out/thumbnail.jpg`) ست می‌شود
- **زیرنویس فارسی** (`build/subtitles.srt`) با language=fa آپلود می‌شود
- نتیجه در `out/upload-youtube.json` ذخیره می‌شود (video_id، لینک، هش تأیید)

## دروازه‌ی تأیید

آپلود **بدون تأیید انجام نمی‌شود**؛ اگر ویدیو بعد از تأیید عوض شده باشد، آپلود رد می‌شود
(هش SHA-256 چک می‌شود). برای تأیید:

```bash
python -m telton publish -p <slug> --by "اسم تو"      # تأیید + پکیج
python -m telton youtube upload -p <slug> --privacy unlisted
```

## خطاهای رایج

| خطا | معنا | راه‌حل |
|---|---|---|
| `accessNotConfigured` | API فعال نیست | مرحله ۱.۲ را انجام بده |
| `invalid_grant` / `Token has been expired or revoked` | توکن باطل شده | `python -m telton youtube auth` دوباره |
| `403 forbidden` روی تامبنیل | کانال تأیید نشده یا زیر ۵۰ مشترک نیست | تامبنیل را دستی در Studio بگذار (آپلود ویدیو موفق است) |
| `quotaExceeded` | سهمیه‌ی روزانه (۱۰٬۰۰۰ واحد؛ هر آپلود ~۱۶۰۰) | فردا امتحان کن |
| `youtube.upload` scope rejected | اکانت Workspace محدود | با اکانت gmail معمولی تست کن |

> نکته: اپ در حالت **Testing** توکن را هر ۷ روز باطل می‌کند؛ برای استفاده‌ی روزانه
> در OAuth consent screen دکمه‌ی **Publish app** را بزن.
