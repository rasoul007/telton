"""Persian text helpers for the narrator.

Two jobs:

1. `vocalize()` adds Arabic/Persian diacritics (اِعراب) to the words a TTS engine
   usually gets wrong (team names, competition names, numbers). Subtitles stay
   clean/undiacritized — only the spoken text is vocalized.
2. `speechify()` makes a written sentence sound like a sports anchor: shorter
   clauses, punctuation for breathing pauses, and no leftover bookish phrasing.
"""

from __future__ import annotations

import re

# Word -> vocalized form. Longest matches win (so «لیگ برتر» beats «لیگ»).
TASHKEEL: dict[str, str] = {
    # مسابقات و مفاهیم
    "ورزش": "وَرزِش",
    "ورزشی": "وَرزِشی",
    "فوتبال": "فوتبال",
    "لیگ": "لیگ",
    "لیگ برتر": "لیگِ بِرتَر",
    "جدول": "جَدوَل",
    "صدر": "صَدر",
    "صدرنشین": "صَدرنِشین",
    "امتیاز": "اِمتِیاز",
    "هفته": "هَفتِه",
    "دقیقه": "دَقیقِه",
    "بازی": "بازی",
    "بازیکن": "بازیکُن",
    "گل": "گُل",
    "گلها": "گُل‌ها",
    "پیروزی": "پیروزی",
    "شکست": "شِکَست",
    "قهرمان": "قَهرِمان",
    "قهرمانی": "قَهرِمانی",
    "قهرمان جهان": "قَهرِمانِ جَهان",
    "جهان": "جَهان",
    "مسابقات": "مُسابِقات",
    "مسابقه": "مُسابِقِه",
    "مدال": "مِدال",
    "طلا": "طَلا",
    "نقره": "نُقرِه",
    "برنز": "بِرُنز",
    "تیم": "تیم",
    "تیم ملی": "تیمِ مِلّی",
    "سرمربی": "سَرُمُرَبّی",
    "کنفرانس": "کُنفِرانْس",
    "پنالتی": "پِنالتی",
    "داور": "داوَر",
    "هوادار": "هَوادار",
    "استادیوم": "اِستادیوم",
    "ورزشگاه": "وَرزِشگاه",
    # کشتی
    "کشتی": "کُشتی",
    "کشتی فرنگی": "کُشتیِ فَرَنگی",
    "فرنگی": "فَرَنگی",
    "آزاد": "آزاد",
    "کشتی آزاد": "کُشتیِ آزاد",
    # باشگاه‌های ایران
    "پرسپولیس": "پِرسِپولیس",
    "استقلال": "اِستِقلال",
    "سپاهان": "سِپاهان",
    "فولاد": "فولاد",
    "تراکتور": "تِراکتور",
    "نساجی": "نِساجی",
    "قائمشهر": "قائِم‌شَهر",
    "فجر سپاسی": "فَجرِ سِپاسی",
    "خیبر": "خِیبَر",
    # باشگاه‌های اروپا
    "آرسنال": "آرسِنال",
    "لیورپول": "لیوِرپول",
    "آنفیلد": "آنفیلد",
    "رئال مادرید": "رِئالِ مادْرید",
    "رئال": "رِئال",
    "مادرید": "مادْرید",
    "بارسلونا": "بارسِلونا",
    "بایرن": "بایرن",
    "دورتموند": "دورتموند",
    "لورکوزن": "لِورکوزِن",
    "اشتوتگارت": "اِشتوتگارت",
    "لایپزیش": "لایپزیش",
    "شالکه": "شالکِه",
    "لاجیو": "لاجیو",
    "سری آ": "سِری‌آ",
    "سری‌آ": "سِری‌آ",
    "یوونتوس": "یووِنتوس",
    "ناپولی": "ناپولی",
    "اینتر": "اینتر",
    "آث میلان": "آ.ث. میلان",
    "منچستریونایتد": "مَنچِستِر یونایتد",
    "منچسترسیتی": "مَنچِستِر سیتی",
    "اسلاویا": "اِسلاویا",
    "اتلتیکو": "اَتلِتیکو",
    "لیگ قهرمانان": "لیگِ قَهرَمانان",
    # افراد
    "هری کین": "هَری کِین",
    "کین": "کِین",
    "امباپه": "اُمباپِه",
    "بلینگام": "بِلینگام",
    "هایورتز": "هایوِرْتز",
    "فان دایک": "فان دایْک",
    "ایزاک": "ایزاک",
    "ایرائولا": "ایرائولا",
    "همیلتون": "هَمیلتون",
    "لکلر": "لِکلِر",
    "آنتونلی": "آنتونِلی",
    "فرشتپن": "فِرشتِپِن",
    "نوریس": "نوریس",
    "راسل": "راسِل",
    # فرمول یک
    "فرمول یک": "فُرمولِ یِک",
    "فرمول": "فُرمول",
    "گراندپری": "گراندپری",
    "قهرمان جهان فرمول یک": "قَهرِمانِ جَهان فُرمولِ یِک",
    # عمومی
    "ایران": "ایران",
    "تهران": "تِهران",
    "آستانه": "آستانِه",
    "قزاقستان": "قَزاقِستان",
    "اینترلاگوس": "اینتِرلاگوس",
    "برزیل": "بِرِزیل",
    "اروپا": "اُروپا",
    "گزارش": "گُزارِش",
    "خبر": "خَبَر",
    "اخبار": "اَخبار",
}

# words that make narration sound like a newspaper instead of a person
STIFF_PHRASES = [
    ("می‌باشد", "ـه"),
    ("می‌باشد.", "ـه."),
    ("گردید", "شد"),
    ("نمود", "کرد"),
    ("در ادامه", "بعدش"),
    ("به گزارش", "طبقِ گزارشِ"),
    ("لازم به ذکر است که", ""),
    ("شایان ذکر است", ""),
]

_WORD_RE = re.compile(r"[\u0600-\u06FF\u200c]+")


def _sorted_keys() -> list[str]:
    return sorted(TASHKEEL, key=len, reverse=True)


def vocalize(text: str) -> str:
    """Add diacritics so the Persian TTS pronounces names correctly."""
    if not text:
        return ""
    out = text
    for key in _sorted_keys():
        spoken = TASHKEEL[key]
        # whole-word match only (Persian letters + ZWNJ)
        out = re.sub(rf"(?<![\u0600-\u06FF]){re.escape(key)}(?![\u0600-\u06FF])", spoken, out)
    return out


def speechify(text: str) -> str:
    """Make a written sentence sound spoken: drop stiff phrasing, add pauses."""
    if not text:
        return ""
    out = text
    for stiff, friendly in STIFF_PHRASES:
        out = out.replace(stiff, friendly)
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


# Latin tokens and abbreviations that Persian TTS reads badly -> Persian spelling
LATIN_SAY = {
    "F1": "اف یک",
    "VAR": "وی ای آر",
    "UCL": "یو سی ال",
    "NBA": "ان بی ای",
    "NFL": "ان اف ال",
    "FIFA": "فیفا",
    "AFC": "ای اف سی",
    "GP": "گراند پری",
    "FC": "اف سی",
    "TV": "تی وی",
    "AI": "هوش مصنوعی",
}

# extra respellings for words the TTS still gets wrong (key = what we write,
# value = what the engine should literally read)
SAY_AS = {
    "پرسپولیس": "پِرسِپُلیس",
    "استقلال": "اِستِقلال",
    "سپاهان": "سِپاهان",
    "نساجی": "نِساجی",
    "تراکتور": "تِراكتور",
    "لیورپول": "لیوِرپول",
    "آرسنال": "آرسِنال",
    "آنفیلد": "آنفیلد",
    "امباپه": "اُمباپِه",
    "بلینگام": "بِلینگام",
    "هایورتز": "هایوِرْتز",
    "ایرائولا": "ایرائولا",
    "کیمی": "کیمی",
    "آنتونلی": "آنتونِلّی",
    "فرشتپن": "فِرستَپِن",
    "همیلتون": "هَمیلتون",
    "لکلر": "لُکلِر",
    "لاجیو": "لاجّیو",
    "یوونتوس": "یووِنتوس",
    "اینترلاگوس": "اینتِرلاگوس",
    "قائمشهر": "قائِم‌شَهر",
    "فرنگی": "فَرَنگی",
}


def latin_to_persian(text: str) -> str:
    """Replace Latin abbreviations with how a Persian anchor would say them."""
    out = text
    for latin, persian in LATIN_SAY.items():
        out = re.sub(rf"(?<![A-Za-z]){re.escape(latin)}(?![A-Za-z])", persian, out)
    return out


def apply_say_as(text: str) -> str:
    """Force the engine to read tricky words the way we want."""
    out = text
    for written in sorted(SAY_AS, key=len, reverse=True):
        spoken = SAY_AS[written]
        out = re.sub(rf"(?<![\u0600-\u06FF]){re.escape(written)}(?![\u0600-\u06FF])", spoken, out)
    return out


def pause_after_commas(text: str) -> str:
    """Ensure breathing pauses exist so the voice is not flat."""
    out = re.sub(r"،\s*", "، ", text)
    return out


def spoken(text: str) -> str:
    """Full pipeline for TTS input (subtitles keep the original text)."""
    return pause_after_commas(apply_say_as(vocalize(speechify(latin_to_persian(text)))))
