# موزیک پس‌زمینه (بدون مشکل کپی‌رایت)

## ✅ موزیک آماده — ساخته‌ی خودمان
فایل `tooop-sports-bed.mp3` **با کد در `scripts/make_music.py` از صفر ساخته شده** است:
درام، بیس، آرپژ و پد، ۱۲۸ BPM، گام «د مینور قهرمانی»، با پامپ ساید‌چین مثل
تریلرهای ورزشی.

- **لایسنس:** کاملاً اورجینال و مال خودت (هیچ سمپل خارجی در آن نیست) →
  نه Content-ID، نه ری‌استرایت، و می‌توانی monetize کنی.
- نسخه‌ی جدید بساز:
  ```bash
  python scripts/make_music.py --bars 32 --out assets/music/tooop-sports-bed-v2.wav
  ```
  (`bars` = تعداد میزان؛ هر ۸ میزان ≈ ۱۵ ثانیه. برنامه خودش فایل را لوپ می‌کند.)

## جایگزین: موزیک آماده‌ی آزاد
| منبع | لایسنس |
|---|---|
| [YouTube Audio Library](https://studio.youtube.com) → Audio Library | بدون کپی‌رایت |
| [Pixabay Music](https://pixabay.com/music/) | Pixabay License |
| [Uppbeat](https://uppbeat.io) (پلن رایگان) | با کردیت |
| [Free Music Archive](https://freemusicarchive.org) | CC — لایسنس هر ترک را بخوان |
| [Incompetech](https://incompetech.com) | CC BY |

⚠️ از موزیک‌های اصلی تلویزیون/برندها استفاده نکن.
اولین فایل به ترتیب حروف الفبا در این پوشه انتخاب می‌شود.

## داکینگ (خودکار)
موزیک وقتی گوینده حرف می‌زند کم می‌شود و در سکوت‌ها بلند می‌شود.
تنظیم‌ها در `config/style.yaml`:

```yaml
audio:
  music: true
  music_volume: 0.55        # سطح موزیک در سکوت‌ها
  duck_ratio: 8             # شدت کم شدن زیر صدای گوینده
  duck_threshold: 0.045
```

## موزیک مخصوص یک قسمت
```yaml
# projects/<slug>/project.yaml
music: assets/music/tooop-sports-bed-v2.wav
```
