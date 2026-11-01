---
name: social-poster
description: Build a social media poster as HTML/CSS (brand colours, logo, price, buy link, bundled fonts, English and/or Bangla text) around a product render, held to Hallmark's anti-AI-design floor, then export PNGs at 1080x1350 feed, 1080x1920 story and 1200x630 Facebook with Playwright. Use for posters, social posts, ads, or banners from renders.
argument-hint: <product image> ["poster text"]
---

# Social poster

Posters are **HTML/CSS rendered by Chromium**, never drawn with Pillow, ImageMagick or Blender text.
Bangla text must be shaped by the browser with a Bengali font (Hind Siliguri or Noto Sans Bengali).
Pillow can't shape Bengali conjuncts correctly, so it is never used for text.

Every poster must read as designed, not generated. That bar is **Hallmark**
(`~/.claude/skills/hallmark`, installed by setup.ps1). Its Floor applies in full; see section 3.

## 1. Gather inputs

- Workspace: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/studio_config.py"` → `workspace`.
- Product image: the **opaque** `<workspace>/renders/<name>_hero.png`, used full-bleed. The transparent
  render keeps a faint shadow-catcher rectangle, and a cut-out on a glow reads as AI-made.
- Text: the headline and any copy the user gave, exactly as given. If none, write it in the brand
  voice: a headline of 7 words or fewer and one sentence of 12 or fewer, both built on a real fact
  (a dimension, the material, what it does). Never invent claims.
- Price: `cost.suggested_price` from `<workspace>/production/<name>/production.json`. No sheet, no price.
- Brand: `<workspace>/brand.md` if it exists, else `${CLAUDE_SKILL_DIR}/brand.md`: colours, fonts,
  logo files, website, buy link, CTA, licence rule.
- Logo: `<workspace>/brand/borgo-labs-logo-dark.png` (copy it from `${CLAUDE_PLUGIN_ROOT}/brand/` if missing).

## 2. Build the HTML

- Copy `${CLAUDE_SKILL_DIR}/template.html` to `<workspace>/posters/<name>.html`. It is the "drawing
  sheet": the render full-bleed, one real dimension drawn on it, and a title block with the headline,
  the price and buy button, the specs and the design credit. Replace every `{{...}}`.
- **Measure, don't guess.** Read the transparent render's alpha bbox row by row (Pillow + numpy) for
  the dimension line's percentages, and sample the opaque render's corner for `--color-paper`. Move
  `--vx/--vy/--vw` per size until the product sits right. The template's comments say which numbers.
- The signature can change per product (a dimension, a close-up crop of the detail render, the price
  set huge). Keep exactly one, and name it in the stamp.
- Fonts: only name the families; the exporter injects Inter, Space Grotesk, JetBrains Mono,
  Hind Siliguri and Noto Sans Bengali.
- Every Bangla element, the taka sign included: `lang="bn"`, and its **first** `font-family` is
  Hind Siliguri or Noto Sans Bengali (the exporter fails otherwise). Bangla line-height ≥ 1.35, and no
  letter-spacing or `text-transform` on Bangla.
- Sizes: the exporter sets `<html data-size="feed|story|facebook">`.
  - **feed 1080×1350**, **story 1080×1920** (top 250 px and bottom 340 px free of text and logo),
    **facebook 1200×630** (render left, sheet right, headline ≤ 2 lines).
- Logo top-left on feed and story, top-right on Facebook, at least 120 px wide.
- Price and buy link: only with a production sheet, and only after the licence check in brand.md.

## 3. Hallmark floor (none of it waivable)

- Every colour and font goes through a `:root` token. `overflow: clip`, never `hidden`.
- No eyebrow above the headline, and no label in tracked capitals or small caps: labels are the body
  face, a step smaller, in sentence case.
- No middle-dot-joined strings, no arrows glued to text, no decorative dots, no purple-blue gradient,
  no card inside a card, no emoji icons.
- No invented number, testimonial or logo. About 80 words at most.
- Spacing on the 4 px scale, at most 3 font families (waive 37 for the taka sign's Hind Siliguri).
- The CSS starts with the Hallmark stamp and critique line (the template has them; fill them in).
  Waivers use `/* Hallmark · waive <id> · <selector> · <reason> */`.

Lint before every export and fix every FAIL; fix or waive every REFLEX:

```
node "$HOME/.claude/skills/hallmark/scripts/sloplint.mjs" "<workspace>/posters/<name>.html" --genre modern-minimal
```

(Skip `--render`: it checks web layouts at eight widths, which a fixed-size poster doesn't have.)

## 4. Export

```
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/export_poster.py" "<workspace>/posters/<name>.html" --name <name>
```

This writes `<workspace>/posters/<name>_feed.png`, `_story.png` and `_facebook.png` (`--sizes feed,story`
to limit, `--out DIR` to redirect). The last line is JSON; `ok: false` with `problems` means some Bangla
text (or ৳) isn't in a Bengali font, so fix the CSS and export again.

## 5. Check your work

Open each PNG with the Read tool and check: nothing clipped or overlapping, the buy button clear of the
bottom edge, Bangla conjuncts right (ক্ষ, ন্ত, র‍্য), the logo visible, the story safe zones clear, the
product whole. Fix and re-export until all three are clean.

## 6. Report

Return the HTML path, the three PNG paths, the sloplint summary line, and whether a price and buy
link are on the poster (and the licence note if it's someone else's design).
