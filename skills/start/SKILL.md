---
name: start
description: Main entry point of Alif's 3D Agent. Asks for the product link or file, then the requirements (lamp, printer, filament and colour, part or kit, quantity, poster language and text), then runs the whole pipeline - download, licence check, fit check, production sheet PDF (material, colour, grams, print time, cost and selling price in BDT), Blender render, and posters with logo, price and buy link - and ends by updating the agent's CLAUDE.md and pushing it to GitHub. Use when the user calls the 3D agent or gives a model link to turn into a product.
argument-hint: [link or file]
---

# /start

Arguments: `$ARGUMENTS` (a link or file, or nothing).

## 0. Context

- `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/studio_config.py"` → `workspace`; `_path` is the clone's
  local.config.json, so its folder is the **clone** (the GitHub repo).
- Read `<clone>/CLAUDE.md` (agent notes and learnings) before anything else and follow it.
- The other skills and agents (`fit-check`, `product-render`, `social-poster`) hold the details.
  Read their SKILL.md when you run a step yourself instead of delegating it.

## 1. The product

If `$ARGUMENTS` is empty, ask exactly this and stop until they answer:
> Send me the product: a link (Printables, Thingiverse, MakerWorld, direct file) or a file path.

Pick `name`: a short lowercase slug from the model title. Then get the files into
`<workspace>/input/<name>/`:
- **Printables, Thingiverse, direct links, local files**: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/fetch_model.py" "<link or path>" --name <name>`.
- **MakerWorld and other login sites**: never script the download or work around the login or bot
  check. Instead:
  1. Read the public metadata, which is allowed:
     `https://makerworld.com/api/v1/design-service/design/<id>` gives `title`, `license`, and
     `instances[]` with `title`, `prediction` (print seconds) and `weight` (g) per print profile.
  2. Open the page in the user's browser: `Start-Process "<url>"`, and tell them to click Download.
  3. Watch `~/Downloads` for a new `.3mf/.stl/.step/.obj/.zip` (a background loop, 30 min). When it
     lands, copy it into `<workspace>/input/<name>/`, unzip a zip into its own folder, and continue
     with `fetch_model.py <path>`.
- Several variants (e.g. `E14` and `E26-E27`): pick the one that matches the lamp answer below.
- **Licence**: note the model's licence (MakerWorld `license`, the Printables or Thingiverse page).
  Personal-use, non-commercial or "standard digital file" licences don't allow selling prints.

## 2. Requirements

Ask with AskUserQuestion, all four in one call (first option = default):
1. **Lamp**: AC lamp (E27 holder) / DC lamp (USB puck light) / Check both / Not a lamp part.
2. **Printer**: Bambu A1 / Bambu P1S / Bambu X1C / Bambu A1 mini.
3. **Filament**: PLA Matte / PLA Basic / PETG / PLA+.
4. **Colour**: Bone white / Matte black / Copper orange / Grey.

Then a second call:
1. **Sell as**: Part only / Kit with the lamp hardware (the kit for the chosen lamp in pricing.json).
2. **Quantity**: 1 / 5 / 10 / 20.
3. **Poster language**: English / Bangla / Both (Bangla headline, English specs).
4. **Poster text**: Write it for me / I'll give it (they type it under Other).

If the licence doesn't allow selling, add a third call with one question: *"This design is
<licence>. Add a price and buy link anyway?"* → Yes, I have the designer's permission / No, showcase only.

If the user says "go ahead" or skips, take the defaults and list them in one line.

## 3. Fit check (skip for "Not a lamp part")

Delegate to the `alifs-3d-agent:fit-inspector` agent with the model files, lamp choice, name and
workspace. It returns the verdict, report.md and `renders/<name>.blend`. If the verdict isn't `fits`,
show the report and ask whether to continue. If it's not a lamp part, import the model into a new
Blender scene, centre it on the ground and save `renders/<name>.blend` yourself.

## 4. Production sheet (run it in the background while the render runs)

```
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/production.py" <model files> --name <name> --title "<title>"
    --printer <A1|P1S|X1C|A1 mini> --filament "<filament>" --color "<colour>" --qty <n>
    [--hardware "<item>=<BDT>" ... for a kit, from pricing.json "kits"]
    --source "<link>" --license "<licence>" --credit "<designer, when not ours>"
    --image "<workspace>/renders/<name>_hero.png"   (add it on a re-run once the render exists)
```

It slices with Bambu Studio (falls back to a volume estimate without it) and writes
`<workspace>/production/<name>/production.pdf`: the materials, colour, grams and metres of filament,
print time, cost breakdown, and the suggested selling price in BDT. Rates live in
`<clone>/pricing.json`. When MakerWorld gave a `prediction`/`weight` for the same profile, say how the
two compare in one line.

## 5. Render

Delegate to `alifs-3d-agent:render-artist` with `renders/<name>.blend` (an assembly: don't re-import),
the filament and colour as the printed part's material, and the studio mood. Re-run production.py with
`--image` once `<name>_hero.png` exists, so the PDF shows the product.

## 6. Posters

Delegate to `alifs-3d-agent:poster-designer` with: the opaque hero render, the poster text or "write
it", the language, `production.json` for the price, the buy link from brand.md, and the licence answer
(showcase only means no price and no buy link). It follows Hallmark and brand.md.

## 7. Report

| Step | Result |
|---|---|
| Source | link, licence, files |
| Fit | verdict, clearance, similarity (say if provisional) |
| Production | grams, print time, cost, suggested price; PDF path |
| Blender scene | renders/<name>.blend |
| Renders | hero, front, detail (+ transparent) |
| Posters | feed, story, facebook PNG paths |

Use absolute paths, then one line on what needs the user (licence, measurements, prices to confirm).

## 8. Update the agent's notes and GitHub

Every run ends here, even a partial one:
1. Append one line to `## Log` in `<clone>/CLAUDE.md`: date, product, lamp verdict, grams, print time,
   price.
2. Add anything a future run should know (a site quirk, a script bug, a fix that worked) to
   `## Learnings`. Keep entries one or two lines; merge with an existing entry instead of repeating it.
3. `git -C <clone> add CLAUDE.md`, commit (`notes: <name>`), and `git -C <clone> push`.
   If you changed skills, agents or scripts, bump `version` in `.claude-plugin/plugin.json` in the same
   commit, so other PCs pick the change up.
