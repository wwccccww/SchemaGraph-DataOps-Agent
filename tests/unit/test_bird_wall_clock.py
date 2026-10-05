"""BIRD Gold 墙钟锚定到 anchor_date。"""

from __future__ import annotations

from app.evaluation.bird import adapt_bird_wall_clock, load_bird_cases
from app.evaluation.external_gold import wall_clock_sensitive


def test_frozen_bird_gold_is_not_wall_clock_sensitive() -> None:
    for case in load_bird_cases():
        assert not wall_clock_sensitive(case.gold_sql), case.id


def test_adapt_replaces_sqlite_now() -> None:
    sql = (
        "SELECT strftime('%Y', 'now') - strftime('%Y', birth_date) AS age "
        "FROM client WHERE strftime('%m-%d', 'now') < strftime('%m-%d', birth_date)"
    )
    adapted = adapt_bird_wall_clock(sql)
    assert "now" not in adapted.lower()
    assert "2026-10-01" in adapted
