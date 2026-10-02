# Team Tennent's website

Static site built with [Astro](https://astro.build), deployed to GitHub Pages.

## Run it locally

```sh
npm install
npm run dev      # http://localhost:4321/
npm run build    # output in dist/
```

## Updating content

| What | Where |
|---|---|
| Next tournament (home page hero) | `src/data/tournament.json` |
| Players | `src/data/team.json` |
| Results | `src/data/accomplishments.json` |
| Blog posts | `src/content/blog/*.md` |

### Photos

- Player photo: put the file in `public/images/team/` and set `"photo": "allyg.jpg"` for that player in `team.json`. Square images work best.
- Home page team photo: put the file in `public/images/` and set `"photo": "team.webp"` in `tournament.json`.
- The wide photo on the team page is still a placeholder in `src/pages/team.astro`.

Anything with `"photo": null` shows a placeholder.

### Accomplishments

Results are pulled from [hri.gg](https://hri.gg) with a script (Python 3, nothing to install):

```sh
python3 scripts/update_accomplishments.py --dry-run   # show what would change
python3 scripts/update_accomplishments.py             # update src/data/accomplishments.json
python3 -m unittest discover scripts                  # run the script's tests
```

It keeps Top 8 or better at Planetary Qualifiers and Top 64 or better everywhere else, sorted newest first.
Players and pages to scrape are in `scripts/accomplishments_config.json`:

- `players` maps the hri.gg nickname to the name shown on the site.
- `urls` are the pages to scrape; the nickname is added to the end of each. `leaderboard/players` is
  always the current season, so when a new season starts add the one that just ended
  (e.g. `https://hri.gg/leaderboard/season-2/players`).

Entries can still be added by hand; the script keeps anything it did not scrape itself.

```json
[
  { "date": "2026-11-01", "event": "Regional Championship Utrecht", "player": "AllyG", "placing": "Top 16" }
]
```

### New blog post

Create `src/content/blog/my-post.md`:

```md
---
title: Utrecht report
date: 2026-11-02
summary: One line shown in the post list.
---

Post text in Markdown.
```

Add `draft: true` to keep a post off the site.

## Deploying

Pushing to `main` runs `.github/workflows/deploy.yml`. In the GitHub repo, set
**Settings → Pages → Source** to **GitHub Actions** once.

The site is served from `teamtennents.uk`, set under **Settings → Pages → Custom domain**
and as `site` in `astro.config.mjs`.
