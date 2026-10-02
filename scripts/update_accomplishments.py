#!/usr/bin/env python3
"""Scrape hri.gg leaderboard pages and update src/data/accomplishments.json.

    python3 scripts/update_accomplishments.py            # update the file
    python3 scripts/update_accomplishments.py --dry-run  # only print what would change

Players and URLs live in scripts/accomplishments_config.json. Each URL gets
"/<nickname>" appended. Standard library only, no install needed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "accomplishments_config.json"
DATA_PATH = ROOT / "src" / "data" / "accomplishments.json"

USER_AGENT = "Mozilla/5.0 (compatible; team-tennents-website; +https://teamtennents.uk)"
ROW_CLASS = "leaderboard-row"
FIELD_PREFIX = "leaderboard-event-row__"
FIELDS = ("date", "name", "tier", "placement")

# Worst placing that still counts: Champion = 1, Finalist = 2, Top N = N.
PLANETARY_CUTOFF = 8
DEFAULT_CUTOFF = 64


class LeaderboardParser(HTMLParser):
    """Collects date, name, tier and placement of each event row on a player page."""

    def __init__(self):
        super().__init__()
        self.rows = []
        self._row = None
        self._spans = []  # field (or None) of every open <span> inside the row

    def handle_starttag(self, tag, attrs):
        classes = (dict(attrs).get("class") or "").split()
        if tag == "a" and ROW_CLASS in classes:
            self._row = {f: "" for f in FIELDS}
            self._spans = []
        elif tag == "span" and self._row is not None:
            field = None
            for c in classes:
                if c.startswith(FIELD_PREFIX) and c[len(FIELD_PREFIX):] in FIELDS:
                    field = c[len(FIELD_PREFIX):]
            self._spans.append(field)

    def handle_endtag(self, tag):
        if self._row is None:
            return
        if tag == "span" and self._spans:
            self._spans.pop()
        elif tag == "a":
            self.rows.append({f: " ".join(v.split()) for f, v in self._row.items()})
            self._row = None

    def handle_data(self, data):
        # text belongs to the innermost span only, so the tier badge nested in
        # the name span does not end up in the event name
        if self._row is not None and self._spans and self._spans[-1]:
            self._row[self._spans[-1]] += data


def parse_rows(html):
    parser = LeaderboardParser()
    parser.feed(html)
    return parser.rows


def parse_date(text):
    """hri.gg shows US style dates ("Sep 6, 2026"); the JSON keeps ISO (2026-09-06)."""
    return datetime.strptime(text.strip(), "%b %d, %Y").date().isoformat()


def eu_date(iso):
    """2026-09-06 -> 06/09/2026, for messages."""
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def normalize_placing(text):
    """"TOP 4" -> "Top 4", "CHAMPION" -> "Champion"."""
    return " ".join(text.split()).title()


def placing_rank(placing):
    """Champion = 1, Finalist = 2, Top N = N. None for anything else, e.g. "Day 2"."""
    p = placing.strip().lower()
    if p == "champion":
        return 1
    if p == "finalist":
        return 2
    m = re.fullmatch(r"top (\d+)", p)
    return int(m.group(1)) if m else None


def is_planetary(event, tier=""):
    return tier.strip().upper() == "PLANETARY" or event.lower().startswith("planetary qualifier")


def qualifies(event, tier, placing):
    rank = placing_rank(placing)
    if rank is None:
        return False
    return rank <= (PLANETARY_CUTOFF if is_planetary(event, tier) else DEFAULT_CUTOFF)


def rows_to_entries(rows, player):
    entries = []
    for row in rows:
        placing = normalize_placing(row["placement"])
        if qualifies(row["name"], row["tier"], placing):
            entries.append({
                "date": parse_date(row["date"]),
                "event": row["name"],
                "player": player,
                "placing": placing,
            })
    return entries


def key(entry):
    return (entry["date"], entry["event"], entry["player"])


def sort_entries(entries):
    """Newest first; within a day by event, then best placing, then player."""
    ordered = sorted(entries, key=lambda e: (e["event"], placing_rank(e["placing"]) or 10**6, e["player"]))
    return sorted(ordered, key=lambda e: e["date"], reverse=True)


def merge(existing, scraped):
    """Scraped results win over existing ones for the same date, event and player.

    Existing entries that were not scraped are kept, so hand-added results survive.
    """
    merged = {key(e): e for e in existing}
    merged.update({key(e): e for e in scraped})
    return sort_entries(merged.values())


def diff(existing, merged):
    """Returns (added, changed) where changed holds (old, new) pairs."""
    old = {key(e): e for e in existing}
    added = [e for e in merged if key(e) not in old]
    changed = [(old[key(e)], e) for e in merged if key(e) in old and old[key(e)]["placing"] != e["placing"]]
    return added, changed


def format_entries(entries):
    """One entry per line, same layout as the hand-written file."""
    if not entries:
        return "[]\n"
    lines = ["  " + json.dumps(e, ensure_ascii=False) for e in entries]
    return "[\n" + ",\n".join(lines) + "\n]\n"


def build_url(base, nickname):
    return base.rstrip("/") + "/" + urllib.parse.quote(nickname)


def fetch(url):
    """Returns the page HTML, or None when the page does not exist (404)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def scrape(config, fetch_page=None, delay=0.3, log=print):
    fetch_page = fetch_page or fetch
    entries = {}
    for nickname, player in config["players"].items():
        for base in config["urls"]:
            url = build_url(base, nickname)
            html = fetch_page(url)
            if html is None:
                log(f"  warning: not found, skipped: {url}")
                continue
            for entry in rows_to_entries(parse_rows(html), player):
                entries[key(entry)] = entry
            if delay:
                time.sleep(delay)
    return sort_entries(entries.values())


def load_config(path=CONFIG_PATH):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if not config.get("urls") or not config.get("players"):
        raise ValueError(f"{path} needs a non-empty 'urls' list and 'players' map")
    return config


def describe(entry):
    return f"{eu_date(entry['date'])}  {entry['event']}: {entry['player']} ({entry['placing']})"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print changes without writing the file")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--output", type=Path, default=DATA_PATH)
    args = parser.parse_args(argv)

    config = load_config(args.config)
    existing = json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else []

    print(f"Scraping {len(config['players'])} players x {len(config['urls'])} URLs...")
    try:
        scraped = scrape(config)
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"error: scraping failed, file left untouched: {e}", file=sys.stderr)
        return 1

    merged = merge(existing, scraped)
    added, changed = diff(existing, merged)
    for e in added:
        print(f"  + {describe(e)}")
    for old, new in changed:
        print(f"  ~ {describe(new)}, was {old['placing']}")

    scraped_keys = {key(e) for e in scraped}
    for e in existing:
        if key(e) not in scraped_keys:
            print(f"  kept, not among the scraped results: {describe(e)}")

    text = format_entries(merged)
    if args.output.exists() and args.output.read_text(encoding="utf-8") == text:
        print("Already up to date.")
    elif args.dry_run:
        print(f"Dry run: {len(added)} added, {len(changed)} changed, nothing written.")
    else:
        args.output.write_text(text, encoding="utf-8")
        print(f"Wrote {len(merged)} results to {args.output} ({len(added)} added, {len(changed)} changed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
