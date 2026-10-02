"""Run with: python3 -m unittest discover scripts"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import update_accomplishments as ua


def row(date, name, tier, placement):
    """An event row with the same markup as hri.gg."""
    return f"""
          <a class="leaderboard-row" href="/players/AllyG/tournaments/413461">
            <span class="leaderboard-event-row__date">
              {date}
            </span>
            <span class="leaderboard-event-row__name">
              {name}
              <span class="leaderboard-event-row__tier">{tier}</span>
            </span>
            <span class="leaderboard-event-row__placement">
              {placement}
            </span>
            <span class="leaderboard-event-row__points leaderboard-event-row__points--low">
              +25
              <span class="leaderboard-event-row__points-label">pts</span>
            </span>
            <span class="leaderboard-event-row__hri">
                <span class="leaderboard-event-row__hri-delta leaderboard-event-row__hri-delta--up">
                  +3
                </span>
                  <span class="leaderboard-event-row__hri-after">
                    &rarr; 1,948
                  </span>
            </span>
</a>"""


def page(*rows):
    return f"""<!DOCTYPE html><html><body>
      <a class="nav-link" href="/leaderboard">Leaderboard</a>
      <main>{''.join(rows)}</main>
      <a class="site-footer__link" href="/docs">Docs</a>
    </body></html>"""


def entry(date, event, player, placing):
    return {"date": date, "event": event, "player": player, "placing": placing}


class ParseRowsTest(unittest.TestCase):
    def test_extracts_fields(self):
        html = page(
            row("Apr 5, 2026", "Planetary Qualifier Stockport", "PLANETARY", "TOP 4"),
            row("Jan 31, 2026", "Sector Qualifier Paris", "SECTOR", "TOP 64"),
        )
        self.assertEqual(ua.parse_rows(html), [
            {"date": "Apr 5, 2026", "name": "Planetary Qualifier Stockport", "tier": "PLANETARY", "placement": "TOP 4"},
            {"date": "Jan 31, 2026", "name": "Sector Qualifier Paris", "tier": "SECTOR", "placement": "TOP 64"},
        ])

    def test_tier_badge_is_not_part_of_event_name(self):
        rows = ua.parse_rows(page(row("May 22, 2026", "Regional Championship Limited Prague", "REGIONAL", "TOP 64")))
        self.assertEqual(rows[0]["name"], "Regional Championship Limited Prague")

    def test_html_entities_in_event_name(self):
        rows = ua.parse_rows(page(row("May 22, 2026", "Tennent&#39;s Cup &amp; Open", "OPEN EVENT", "TOP 8")))
        self.assertEqual(rows[0]["name"], "Tennent's Cup & Open")

    def test_page_without_events(self):
        self.assertEqual(ua.parse_rows(page("<p>No qualifying events yet.</p>")), [])

    def test_other_links_are_ignored(self):
        self.assertEqual(len(ua.parse_rows(page(row("Apr 5, 2026", "Sector Qualifier Paris", "SECTOR", "TOP 4")))), 1)


class DateTest(unittest.TestCase):
    def test_us_page_date_becomes_iso(self):
        self.assertEqual(ua.parse_date("Sep 6, 2026"), "2026-09-06")
        self.assertEqual(ua.parse_date("Dec 13, 2025"), "2025-12-13")
        self.assertEqual(ua.parse_date("  May 2, 2026 "), "2026-05-02")

    def test_bad_date_raises(self):
        with self.assertRaises(ValueError):
            ua.parse_date("06/09/2026")

    def test_eu_date_is_day_first(self):
        self.assertEqual(ua.eu_date("2026-09-06"), "06/09/2026")


class PlacingTest(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(ua.normalize_placing("TOP 4"), "Top 4")
        self.assertEqual(ua.normalize_placing("CHAMPION"), "Champion")
        self.assertEqual(ua.normalize_placing(" top   16 "), "Top 16")
        self.assertEqual(ua.normalize_placing("DAY 2"), "Day 2")

    def test_rank(self):
        self.assertEqual(ua.placing_rank("Champion"), 1)
        self.assertEqual(ua.placing_rank("Finalist"), 2)
        self.assertEqual(ua.placing_rank("Top 4"), 4)
        self.assertEqual(ua.placing_rank("TOP 64"), 64)
        self.assertIsNone(ua.placing_rank("Day 2"))
        self.assertIsNone(ua.placing_rank(""))


class QualifiesTest(unittest.TestCase):
    def test_planetary_needs_top_8(self):
        for placing in ("Champion", "Finalist", "Top 4", "Top 8"):
            self.assertTrue(ua.qualifies("Planetary Qualifier Ayr", "PLANETARY", placing), placing)
        for placing in ("Top 16", "Top 32", "Top 64"):
            self.assertFalse(ua.qualifies("Planetary Qualifier Ayr", "PLANETARY", placing), placing)

    def test_other_events_need_top_64(self):
        for event, tier in (
            ("Sector Qualifier Paris", "SECTOR"),
            ("Regional Championship Bilbao Premier", "REGIONAL"),
            ("Galactic Open 2026", "GALACTIC OPEN"),
            ("Open Eternal Sector Berlin", "OPEN EVENT"),
        ):
            for placing in ("Champion", "Finalist", "Top 4", "Top 8", "Top 16", "Top 32", "Top 64"):
                self.assertTrue(ua.qualifies(event, tier, placing), f"{event} {placing}")
            for placing in ("Top 128", "Top 256", "Day 2"):
                self.assertFalse(ua.qualifies(event, tier, placing), f"{event} {placing}")

    def test_planetary_detected_by_name_when_tier_missing(self):
        self.assertFalse(ua.qualifies("Planetary Qualifier Ayr", "", "Top 16"))
        self.assertTrue(ua.qualifies("Planetary Qualifier Ayr", "", "Top 8"))

    def test_planetary_detected_by_tier_when_name_differs(self):
        self.assertFalse(ua.qualifies("PQ Ayr", "PLANETARY", "Top 16"))


class RowsToEntriesTest(unittest.TestCase):
    def test_filters_and_maps_player_name(self):
        html = page(
            row("Sep 6, 2026", "Planetary Qualifier Melton Mowbray", "PLANETARY", "TOP 16"),
            row("Sep 5, 2026", "Planetary Qualifier Bromborough", "PLANETARY", "TOP 8"),
            row("May 9, 2026", "Sector Qualifier London", "SECTOR", "TOP 64"),
            row("Jul 25, 2026", "Galactic Open 2026", "GALACTIC OPEN", "DAY 2"),
        )
        self.assertEqual(ua.rows_to_entries(ua.parse_rows(html), "Techyfiend"), [
            entry("2026-09-05", "Planetary Qualifier Bromborough", "Techyfiend", "Top 8"),
            entry("2026-05-09", "Sector Qualifier London", "Techyfiend", "Top 64"),
        ])


class SortTest(unittest.TestCase):
    def test_newest_first(self):
        entries = [
            entry("2025-12-13", "Planetary Qualifier London", "AllyG", "Top 4"),
            entry("2026-09-26", "Planetary Qualifier Sheffield", "AllyG", "Top 4"),
            entry("2026-01-04", "Planetary Qualifier Ayr", "AllyG", "Champion"),
        ]
        self.assertEqual([e["date"] for e in ua.sort_entries(entries)], ["2026-09-26", "2026-01-04", "2025-12-13"])

    def test_dates_sort_by_calendar_not_by_day_number(self):
        entries = [
            entry("2026-02-28", "A", "AllyG", "Top 4"),
            entry("2026-10-03", "B", "AllyG", "Top 4"),
            entry("2025-12-31", "C", "AllyG", "Top 4"),
        ]
        self.assertEqual([e["event"] for e in ua.sort_entries(entries)], ["B", "A", "C"])

    def test_same_day_by_event_then_placing_then_player(self):
        entries = [
            entry("2026-01-04", "Planetary Qualifier Ayr", "Techyfiend", "Top 8"),
            entry("2026-01-04", "Planetary Qualifier Ayr", "Oli", "Top 4"),
            entry("2026-01-04", "Planetary Qualifier Ayr", "Spuds", "Top 8"),
            entry("2026-01-04", "Planetary Qualifier Ayr", "AllyG", "Champion"),
            entry("2026-01-04", "Open Event Glasgow", "Sam", "Top 64"),
        ]
        self.assertEqual([(e["event"], e["player"]) for e in ua.sort_entries(entries)], [
            ("Open Event Glasgow", "Sam"),
            ("Planetary Qualifier Ayr", "AllyG"),
            ("Planetary Qualifier Ayr", "Oli"),
            ("Planetary Qualifier Ayr", "Spuds"),
            ("Planetary Qualifier Ayr", "Techyfiend"),
        ])


class MergeTest(unittest.TestCase):
    def test_adds_new_and_keeps_manual_entries(self):
        manual = entry("2026-07-25", "Galactic Open 2026", "Sam", "Day 2")
        new = entry("2026-09-26", "Planetary Qualifier Sheffield", "AllyG", "Top 4")
        self.assertEqual(ua.merge([manual], [new]), [new, manual])

    def test_scraped_placing_replaces_existing(self):
        old = entry("2026-09-26", "Planetary Qualifier Sheffield", "AllyG", "Top 8")
        new = entry("2026-09-26", "Planetary Qualifier Sheffield", "AllyG", "Top 4")
        self.assertEqual(ua.merge([old], [new]), [new])

    def test_same_event_different_players_are_separate(self):
        a = entry("2026-08-22", "Planetary Qualifier Aberdeen", "AllyG", "Champion")
        b = entry("2026-08-22", "Planetary Qualifier Aberdeen", "Good Fraser", "Top 4")
        self.assertEqual(ua.merge([a], [b]), [a, b])

    def test_diff(self):
        old = entry("2026-09-26", "Planetary Qualifier Sheffield", "AllyG", "Top 8")
        same = entry("2026-01-04", "Planetary Qualifier Ayr", "AllyG", "Champion")
        fixed = dict(old, placing="Top 4")
        new = entry("2026-10-01", "Sector Qualifier Rome", "Oli", "Top 16")
        added, changed = ua.diff([old, same], ua.merge([old, same], [fixed, new]))
        self.assertEqual(added, [new])
        self.assertEqual(changed, [(old, fixed)])


class FormatTest(unittest.TestCase):
    def test_one_entry_per_line_and_valid_json(self):
        entries = [
            entry("2026-09-26", "Planetary Qualifier Sheffield", "AllyG", "Top 4"),
            entry("2026-09-06", "Planetary Qualifier Melton Mowbray", "Sam", "Top 4"),
        ]
        text = ua.format_entries(entries)
        self.assertEqual(text, (
            '[\n'
            '  {"date": "2026-09-26", "event": "Planetary Qualifier Sheffield", "player": "AllyG", "placing": "Top 4"},\n'
            '  {"date": "2026-09-06", "event": "Planetary Qualifier Melton Mowbray", "player": "Sam", "placing": "Top 4"}\n'
            ']\n'
        ))
        self.assertEqual(json.loads(text), entries)

    def test_empty(self):
        self.assertEqual(json.loads(ua.format_entries([])), [])

    def test_non_ascii_kept_readable(self):
        text = ua.format_entries([entry("2026-09-26", "Sector Qualifier Málaga", "AllyG", "Top 4")])
        self.assertIn("Málaga", text)


class BuildUrlTest(unittest.TestCase):
    def test_appends_nickname(self):
        self.assertEqual(
            ua.build_url("https://hri.gg/leaderboard/season-1/players", "jlegolas_TT"),
            "https://hri.gg/leaderboard/season-1/players/jlegolas_TT",
        )

    def test_trailing_slash(self):
        self.assertEqual(ua.build_url("https://hri.gg/leaderboard/players/", "AllyG"), "https://hri.gg/leaderboard/players/AllyG")

    def test_nickname_is_escaped(self):
        self.assertEqual(ua.build_url("https://hri.gg/players", "a b"), "https://hri.gg/players/a%20b")


CONFIG = {
    "urls": ["https://hri.gg/leaderboard/players", "https://hri.gg/leaderboard/season-1/players"],
    "players": {"AllyG": "AllyG", "AkkoTT": "Oli"},
}
PAGES = {
    "https://hri.gg/leaderboard/players/AllyG": page(
        row("Sep 26, 2026", "Planetary Qualifier Sheffield", "PLANETARY", "TOP 4"),
    ),
    "https://hri.gg/leaderboard/season-1/players/AllyG": page(
        # same result listed on two pages must only appear once
        row("Sep 26, 2026", "Planetary Qualifier Sheffield", "PLANETARY", "TOP 4"),
        row("Jan 4, 2026", "Planetary Qualifier Ayr", "PLANETARY", "CHAMPION"),
        row("Jan 10, 2026", "Sector Qualifier Tilburg", "SECTOR", "TOP 128"),
    ),
    "https://hri.gg/leaderboard/players/AkkoTT": page("<p>No qualifying events yet.</p>"),
    "https://hri.gg/leaderboard/season-1/players/AkkoTT": page(
        row("Jan 4, 2026", "Planetary Qualifier Ayr", "PLANETARY", "TOP 4"),
    ),
}


class ScrapeTest(unittest.TestCase):
    def test_all_players_and_urls(self):
        requested = []

        def fake_fetch(url):
            requested.append(url)
            return PAGES[url]

        result = ua.scrape(CONFIG, fetch_page=fake_fetch, delay=0, log=lambda m: None)
        self.assertEqual(sorted(requested), sorted(PAGES))
        self.assertEqual(result, [
            entry("2026-09-26", "Planetary Qualifier Sheffield", "AllyG", "Top 4"),
            entry("2026-01-04", "Planetary Qualifier Ayr", "AllyG", "Champion"),
            entry("2026-01-04", "Planetary Qualifier Ayr", "Oli", "Top 4"),
        ])

    def test_missing_page_is_skipped_with_warning(self):
        warnings = []
        pages = dict(PAGES, **{"https://hri.gg/leaderboard/players/AkkoTT": None})
        result = ua.scrape(CONFIG, fetch_page=pages.get, delay=0, log=warnings.append)
        self.assertEqual(len(result), 3)
        self.assertEqual(len(warnings), 1)
        self.assertIn("https://hri.gg/leaderboard/players/AkkoTT", warnings[0])


class ConfigTest(unittest.TestCase):
    def test_repo_config_is_valid(self):
        config = ua.load_config()
        self.assertEqual(config["players"]["AkkoTT"], "Oli")
        self.assertEqual(config["players"]["Fraser_TT"], "Evil Fraser")
        self.assertEqual(len(config["players"]), 11)
        for url in config["urls"]:
            self.assertTrue(url.startswith("https://"), url)

    def test_empty_config_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text('{"urls": [], "players": {}}')
            with self.assertRaises(ValueError):
                ua.load_config(path)


class MainTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.config = Path(tmp.name) / "config.json"
        self.config.write_text(json.dumps(CONFIG))
        self.output = Path(tmp.name) / "accomplishments.json"
        self.manual = entry("2026-07-25", "Galactic Open 2026", "Sam", "Day 2")
        self.output.write_text(json.dumps([self.manual]))
        self.args = ["--config", str(self.config), "--output", str(self.output)]

    def run_main(self, *extra, fetch=PAGES.get):
        with mock.patch.object(ua, "fetch", fetch), mock.patch.object(ua.time, "sleep"), \
                mock.patch("builtins.print"):
            return ua.main(self.args + list(extra))

    def test_writes_merged_sorted_file(self):
        self.assertEqual(self.run_main(), 0)
        self.assertEqual(json.loads(self.output.read_text()), [
            entry("2026-09-26", "Planetary Qualifier Sheffield", "AllyG", "Top 4"),
            self.manual,
            entry("2026-01-04", "Planetary Qualifier Ayr", "AllyG", "Champion"),
            entry("2026-01-04", "Planetary Qualifier Ayr", "Oli", "Top 4"),
        ])

    def test_second_run_changes_nothing(self):
        self.run_main()
        first = self.output.read_text()
        self.run_main()
        self.assertEqual(self.output.read_text(), first)

    def test_dry_run_does_not_write(self):
        before = self.output.read_text()
        self.assertEqual(self.run_main("--dry-run"), 0)
        self.assertEqual(self.output.read_text(), before)

    def test_network_error_leaves_file_untouched(self):
        def broken(url):
            raise ua.urllib.error.URLError("offline")

        before = self.output.read_text()
        with mock.patch("sys.stderr"):
            self.assertEqual(self.run_main(fetch=broken), 1)
        self.assertEqual(self.output.read_text(), before)


if __name__ == "__main__":
    unittest.main()
