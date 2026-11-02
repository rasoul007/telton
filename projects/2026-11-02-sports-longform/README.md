# قسمت ۱۱ آبان ۱۴۰۵ — خبرهای مهم ورزش (۵ دقیقه)

این قسمت با خودِ ایجنت ساخته شده است. خبرها در `stories.json` هستند (۱۶ خبر، همه با `verified: true` و منبع).

## چه چیزی داخل ویدیو است

| بخش | خبرها |
|---|---|
| ورزش ایران | قهرمانی تیمی کشتی فرنگی در جهان (آستانه) + جدول مدال‌ها (ایران دوم با ۱۵ مدال) |
| فوتبال ایران | پرسپولیس ۱–۰ نساجی و بازگشت به صدر / جدول سه‌تایی صدر / برنامه هفته دوازدهم |
| حواشی | جنجال VAR و جمله‌ی ایرائولا / عذرخواهی امباپه / تنش همیلتون–لکلر در فراری |
| فوتبال اروپا | آرسنال ۱–۰ لیورپول در آنفیلد / لاجیو صدرنشین بدون باخت سری‌آ / کلاسیکر و لورکوزن / توپ طلای کین / گل ۵۰ بلینگام / بحران یونایتد |
| جهان ورزش | آنتونلی جوان‌ترین قهرمان تاریخ فرمول یک (۲۰ سال و ۶۸ روز) |
| بعدی | دور چهارم لیگ قهرمانان (اسلاویا–آرسنال، اتلتیکو–بایرن) / گراندپری برزیل |

## خروجی‌ها

| فایل | توضیح |
|---|---|
| `build/script.md` | اسکریپت نهایی با تایم‌کد هر جمله |
| `build/subtitles.srt` | زیرنویس فارسی (چسبیده روی ویدیو) |
| `build/caption.txt` | کپشن آماده + هشتگ + منابع |
| `out/video.mp4` | ویدیوی ۱۰۸۰×۱۹۲۰ با نریشن فارسی (۵:۰۳) |
| `out/thumbnail.jpg` | تامبنیل |
| `out/review.html` | صفحه‌ی بازبینی (تماشا + جدول منابع + چک‌لیست) |
| `out/publish-kit/` | بعد از `approve` ساخته می‌شود |

## بازتولید کامل

```bash
python -m telton build  -p 2026-11-02-sports-longform -d 300
python -m telton voice  -p 2026-11-02-sports-longform -d 300 --rate +10% --no-fit
python -m telton render -p 2026-11-02-sports-longform
python -m telton review -p 2026-11-02-sports-longform    # صفحه‌ی بازبینی
python -m telton approve -p 2026-11-02-sports-longform --by "نام تو"
python -m telton publish -p 2026-11-02-sports-longform
```

## منابع

- BBC Sport: [F1 — Antonelli champion](https://www.bbc.com/sport/formula1/articles/cv62y1e6wly6o) · [Serie A table](https://www.bbc.com/sport/football/italian-serie-a/table) · [La Liga](https://www.bbc.com/sport/football/spanish-la-liga) · [Football](https://www.bbc.com/sport/football)
- ABC News: [Arsenal 1-0 Liverpool + VAR](https://www.abc.net.au/news/2026-11-02/football-arsenal-ends-anfield-drought-liverpool-var-drama/107334968)
- Bundesliga: [Matchday 8](https://www.bundesliga.com/en/bundesliga/matchday)
- UEFA: [Matchday 4 preview](https://www.uefa.com/uefachampionsleague/news/02aa-21f10edb96af-f01ebdbd9935-1000--champions-league-matchday-4-key-stats-and-what-to-look-o/)
- کشتی: [2026 World Wrestling Championships](https://en.wikipedia.org/wiki/2026_World_Wrestling_Championships) · [PersianLeague](https://www.persianleague.com/)
