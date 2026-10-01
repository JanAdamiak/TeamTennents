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
- Home page team photo: put the file in `public/images/` and set `"photo": "team.jpg"` in `tournament.json`.
- The wide photo on the team page is still a placeholder in `src/pages/team.astro`.

Anything with `"photo": null` shows a placeholder.

### Accomplishments

Add entries to `src/data/accomplishments.json`. They are sorted newest first.

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
