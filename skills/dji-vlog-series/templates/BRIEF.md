# BRIEF — <series>

Copy this into the project root. It is the **single source of truth** across sessions: a new
session reads it top to bottom and knows both the settled shape of the series and everything that
has happened. The decision log at the bottom is what makes that true — append to it every time
something is decided, and never rewrite an earlier line.

## Intent

<What the series is, who it is for, and the distinction that matters. Record the choices the user
corrected as corrections, so no later session re-proposes the rejected shape.>

## Assets

- `<source>` — original footage. Read-only: never modify, rename, or delete a source file.
- `<review>/source-metadata.json` — metadata for all N files (step 1).
- `<review>/complete-visual-index.json` — visual index (step 2).
- `<review>/transcripts/` — per-clip transcripts (step 3).
- `<review>/storyboard/` — plan, stills, provenance, `strip.html` (step 4).
- `<review>/clip-review/eNN.json` — per-episode cut lists (step 5).
- `<project>/series.json` — the config every render tool reads: paths, design, text, bed levels.
- `<media>/<proxy set>/` — proxies plus `_ranges.json` (step 6).
- `<project>/assets/fonts/` — the two OFL faces; `<project>/assets/bgm/` — the chosen beds.
- `<project>/layers/eNN/` — the text-layer PNGs the render overlays.
- `<media>/final/` — finals, `eNN.chapters.json`, `thumbnails/`, `qc/`, `YOUTUBE.txt`;
  `<media>/final/draft/` — the lock-gate drafts.

## Customizations

<Per-episode structure, labels, music direction, visual direction, audio policy — everything the
user chose about how it looks and sounds.>

## Notes

- <Confirmed decisions, each attributed to the question it answered.>
- <Defaults you derived rather than asked about — flag them as such.>
- <Constraints: what is off limits, what needs approval, what stays local.>
- <Known footage facts that bound the plan: shortest day, rotation-tagged clips, date range.>

## Decision log

One dated line per decision, newest last. Include what changed, why, and where the artefact lives.
A line here costs nothing and saves a session from re-deriving it.

- `<date>`: <what was decided, and the file that now holds it>
- `<date>`: <the gate that was passed, and by whom>
- `<date>`: <the failure and the fix that worked>
- `<date>`: <status — rendered vs uploaded, stated separately>
