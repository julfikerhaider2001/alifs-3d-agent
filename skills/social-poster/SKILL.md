---
name: social-poster
description: Build a social media poster as HTML/CSS (brand colours, logo, tagline, bundled fonts, English and/or Bangla text) around a product render, then export PNGs at 1080x1350 feed, 1080x1920 story and 1200x630 Facebook with Playwright. Use for posters, social posts, ads, or banners from renders.
argument-hint: <product image> ["poster text"]
---

# Social poster

Posters are **HTML/CSS rendered by Chromium**, never drawn with Pillow, ImageMagick or Blender text.
Bangla text must be shaped by the browser with a Bengali font (Hind Siliguri or Noto Sans Bengali).
Pillow can't shape Bengali conjuncts correctly, so it is never used for text.

## 1. Gather inputs

- Workspace: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/studio_config.py"` → `workspace`.
- Product image: normally `<workspace>/renders/<name>_hero_transparent.png` (transparent, so it sits on
  the brand background). Use the opaque render only for a full-bleed photo look.
- Text: the headline and any copy the user gave. If none, write a short headline from the product
  plus the brand tagline. Don't invent prices, offers or claims.
- Brand: read `<workspace>/brand.md` if it exists, else `${CLAUDE_SKILL_DIR}/brand.md`.
  If it still has `TODO` placeholders, use a neutral palette (#111 text, #F4F1EC background,
  one accent) and tell the user to fill in brand.md.

## 2. Build the HTML

- Copy `${CLAUDE_SKILL_DIR}/template.html` to `<workspace>/posters/<name>.html` and edit it there.
  Keep one HTML file for all three sizes.
- Reference images by path relative to the HTML (e.g. `../renders/<name>_hero_transparent.png`)
  or as absolute `file:///` URLs.
- Fonts: only name the families. The exporter injects them from `${CLAUDE_PLUGIN_ROOT}/fonts`:
  - `"Inter"` for Latin text (variable 100–900)
  - `"Hind Siliguri"` for Bangla headlines (400/500/600/700)
  - `"Noto Sans Bengali"` for Bangla body text (variable 100–900)
- Every Bangla element: `lang="bn"`, and its **first** `font-family` must be Hind Siliguri or
  Noto Sans Bengali (the exporter fails otherwise). Use line-height ≥ 1.35 for Bangla.
  Don't use letter-spacing or `text-transform` on Bangla.
- Layout per size: the exporter sets `<html data-size="feed|story|facebook">`. Write CSS for each,
  e.g. `html[data-size="facebook"] .stage { grid-template-columns: 1fr 1fr; }`.
  - **feed 1080×1350**: product large and centred, headline above or below.
  - **story 1080×1920**: keep the top 250 px and bottom 340 px free of text and logo (app UI covers them).
  - **facebook 1200×630**: landscape, product on one side and text on the other; headline ≤ 2 lines.
- Brand rules from brand.md: colours as CSS variables, the logo in its stated corner at its minimum
  size, and the tagline. Text contrast must be at least 4.5:1.

## 3. Export

```
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/export_poster.py" "<workspace>/posters/<name>.html" --name <name>
```

This writes `<workspace>/posters/<name>_feed.png`, `<name>_story.png` and `<name>_facebook.png`
(`--sizes feed,story` to limit, `--out DIR` to redirect). The last line is JSON; `ok: false` with
`problems` means some Bangla text isn't in a Bengali font, so fix the CSS and export again.

## 4. Check your work

Open each PNG with the Read tool and check: nothing clipped or overlapping, Bangla conjuncts
look right (e.g. ক্ষ, ন্ত, র‍্য), the logo is visible, the story safe zones are clear, and the product
isn't cut off. Fix and re-export until all three are clean.

## 5. Report

Return the HTML path and the three PNG paths with their sizes.
