# Brand sheet

Fill this in once. The poster designer reads it every time.
To use a different brand per workspace, copy this file to `<workspace>/brand.md`; that copy wins.
Replace every `TODO`.

Source: Borgo Labs Brand Guidelines v2.0 (2026).

## Identity
- Brand name: Borgo Labs
- Website / handle: borgo-labs.xyz · info@borgo-lab.xyz · +880 1835 488814
- Buy link (on every poster with a price): borgo-labs.xyz/shop (the Borgo Shop page; use a product page instead once one exists)
- What we do: IoT products, robotics systems and 3D-printed hardware, prototype to production. Uttara, Dhaka.
- Products: Borgo Home (local-first home automation, available) · Borgo Pumps (SMS pump controller, available) · Borgo Sense (LoRa environmental node, coming soon)

## Colours
Dark mode is the default: ink surfaces, copper leads, cyan only signals "live".
No neon green, no electric blue, no fake depth with opacity.

| Role       | Hex      | Use                                   |
|------------|----------|---------------------------------------|
| primary    | #D97B2C  | Molten Copper: headline, CTA background (CTA text in ink #0A0A0B) |
| accent     | #E0995A  | Copper 300: highlights, badges, thin rules |
| background | #0A0A0B  | Ink: poster background (raised panels #15161A / #1E2025) |
| text       | #F4F2EC  | Paper: body text on ink (secondary #D9D6CE, muted #9A9690) |
| live       | #7CD9D9  | Signal Cyan: "live" / online status only, never decoration |
| logo       | #FE7028  | Logo Orange: inside the logo only, never for text or shapes |

Light version (only when a light poster is asked for): background bone #FAF8F3, text ink #0A0A0B, primary copper #D97B2C.

## Logo
- Files (transparent PNG, from Brand Guidelines v2.0 p.4-5), in `${CLAUDE_PLUGIN_ROOT}/brand/` and copied to `<workspace>/brand/`:
- Light-background version: `brand/borgo-labs-logo-light.png` (BORGO orange, LABS charcoal)
- Dark-background version: `brand/borgo-labs-logo-dark.png` (BORGO orange, LABS white), the default, since posters are dark
- Logomark only: `brand/borgo-labs-logomark.png` (avatars, tight spaces)
- Placement: top-left (feed/story) · top-right (facebook)
- Minimum width: 120 px full logo, 24 px logomark · clear space: the height of the LABS wordmark on every side
- Never redraw, recolour, stretch, rotate, fade or add effects; never on low contrast or busy imagery.

## Tagline
- English: Build the physical.
- বাংলা: TODO

## Typography
- Headline (Latin): Space Grotesk 500–700, letter-spacing -0.02em to -0.04em, line-height ~1.08
- Body (Latin): Inter 400 / 600
- Specs, part numbers, telemetry, prices: JetBrains Mono 400
- Bangla headline: Hind Siliguri 600–700
- Bangla body: Noto Sans Bengali 400–500
- Language mix: TODO (e.g. "Bangla headline, English product name")

## Voice and rules
- Tone: engineers who ship - plain, specific, confident. Lead with what the hardware does, then why it matters in the field.
- Always: specs over superlatives ("works without internet", not "revolutionary"); show real installations, not the lab bench; prices in ৳ (3D printing is per gram: PLA ৳6, PLA+ 2.0 / PETG ৳7, ABS ৳8).
- Never: hype words, neon/LED colours, cyan as decoration, Logo Orange outside the logo, stock photos.
- Product renders: matte black + copper edging, small cyan status lights, soft top-left light.
- Call to action: "Buy now" + the buy link when the poster shows a price; "Get a quote" for custom work (Bangla: TODO)

## Price on posters
- Use the suggested price from `<workspace>/production/<name>/production.json` (`cost.suggested_price`), set as `৳630` with the taka sign in Hind Siliguri.
- Never invent a price. No production sheet yet: run production.py first, or leave the price off.
- Someone else's design under a personal-use or non-commercial licence: tell the user before adding a price or buy link; they need the designer's permission to sell prints.
