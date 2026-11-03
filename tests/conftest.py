"""Shared fixtures: a tiny throwaway project so tests never touch real episodes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from telton.config import Project  # noqa: E402

STORIES = [
    {
        "id": "alpha",
        "bucket": "iran_football",
        "priority": 1,
        "headline": "پرسپولیس صدرنشین شد",
        "summary": "پرسپولیس با برد یک بر صفر در قائمشهر به صدر جدول برگشت.",
        "facts": ["نساجی ۰ – ۱ پرسپولیس", "۲۳ امتیاز"],
        "sources": [{"name": "PersianLeague", "url": "https://example.com/a"}],
        "verified": True,
        "tags": ["پرسپولیس", "لیگ برتر"],
    },
    {
        "id": "beta",
        "bucket": "europe_football",
        "priority": 2,
        "headline": "آرسنال آنفیلد را فتح کرد",
        "summary": "آرسنال بعد از چهارده سال با گل هایورتز در آنفیلد برد.",
        "facts": ["لیورپول ۰ – ۱ آرسنال"],
        "sources": [{"name": "BBC Sport", "url": "https://example.com/b"}],
        "verified": True,
        "tags": ["آرسنال", "لیورپول"],
    },
    {
        "id": "gamma",
        "bucket": "world",
        "priority": 3,
        "headline": "جوان‌ترین قهرمان فرمول یک",
        "summary": "آنتونلی در بیست سال و شصت‌وهشت روز قهرمان جهان شد.",
        "facts": ["۲۰ سال و ۶۸ روز"],
        "sources": [{"name": "BBC Sport", "url": "https://example.com/c"}],
        "verified": True,
        "tags": ["فرمول یک", "آنتونلی"],
    },
]


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    proj = Project("test-episode", root=tmp_path / "projects" / "test-episode")
    proj.ensure()
    (proj.root / "project.yaml").write_text(
        "slug: test-episode\ntitle: \"تست\"\nintro: \"سلام\"\noutro: \"خداحافظ\"\n",
        encoding="utf-8",
    )
    (proj.stories_path).write_text(json.dumps(STORIES, ensure_ascii=False), encoding="utf-8")
    return proj
