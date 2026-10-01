# Build — steps 6–8: proxies, layers, music, stamps, captions, thumbnails, lock

## 6. Proxies

`python scripts/make_proxies.py --cut-lists <review>/clip-review --frame-index <review>/frame-index.json --source <source> --out <media>/clips-4k --size 4k --no-autorotate 0035,0064,0134`

One proxy per source file, spanning `min(in) − handle … max(out) + handle` across **every** use of
that file in the series, so a clip two episodes share stays one file. Re-runs skip proxies that
already cover their range.

- **Final geometry, constant fps, `setsar=1`** — the proxy is already the render canvas, so the
  episode graph only cuts and overlays. Cut proxies at the **final** resolution: a 1080p set
  cannot produce a 4K final, and the re-cut costs an hour.
- **`-noautorotate -display_rotation 0`** on the clip numbers whose rotation tag is wrong for
  landscape content (collected at step 1). Fixing it here means the render, the stills and the
  teaser all agree.
- **GOP 2 s** (`--gop`) is a size/seek compromise only; nothing downstream depends on keyframe
  density.
- NVENC first, `libx264 -crf 20` as the automatic fallback: a handful of clips reject the GPU path.

`_ranges.json` records each proxy's `offset`. The renderer seeks `source_time − offset`, so set
`proxies` in `series.json` to this directory and leave the paths alone.

*Done when* every proxy probes at the target geometry and constant fps and `_ranges.json` covers
every clip the cut lists use.

## 7. Fonts, layers, music, stamps, captions, thumbnails

**Fonts.** `python scripts/fetch_fonts.py --out <project>/assets/fonts` once per project: the
Montserrat variable face and IBM Plex Mono with their OFL licences. `design.fonts.sans` / `.mono`
in `series.json` point at the two files; `sans_weight` picks the variable instance.

**Text layers.** `scripts/textlayers.py` draws four kinds with Pillow:

| Layer | Where | Text from |
|---|---|---|
| title card | over the opening shot, `title_hold` seconds | `text.series_line`, the episode `title`, `batch` |
| place stamp | one per beat from beat 2, `stamp_hold` seconds | `stamps.json` place + time of day from the filename hour |
| end card | `end_hold` seconds after the last shot | `text.end_*` plus `text.credit` |
| thumbnail | a 1280×720 JPEG beside the finals, not in the video | `text.thumb_eyebrow` + the title in `thumbnails.json` |

`build_episodes.py` writes the video ones as PNGs into `<project>/layers/eNN/` (config key
`layers`) and overlays them. All sizes, colours and tracking live in the `design` block of
`series.json` and nowhere else; they are canvas pixels tuned at 4K, so a 1080p series sets
`"text_scale": 0.5`. These are FreeType rasters: a series first designed in CSS keeps its design,
not a bit-identical raster.

Preview before rendering: `python scripts/textlayers.py --config series.json --preview <dir>` for
one sample of each kind, or `python scripts/build_episodes.py --config series.json 01
--layers-only` for the real per-episode set.

**Music.** One bed per episode, chosen by the user from candidates you source. Each series gets
its own beds: reusing a previous series' tracks reads as the same video and was rejected on sight.
Procedure: load `/media-use` and `resolve` two or three cleared candidates per slot (CC BY, CC0 or
a catalogue with a ledger record; the licence must cover every platform the series goes to), frozen
under `<project>/assets/bgm-candidates/<slot>/` with a `CANDIDATES.md` (title, artist, source,
licence, exact credit line, duration, why it fits). Give the user the folder path to audition and
wait for one name per slot. Then `loudnorm I=-20 LUFS` the pick, encode AAC into `assets/bgm/`,
write `CREDITS.txt` naming every track, and set `bed` and `text.credit` in `series.json`. The
renderer loops the bed (`-stream_loop -1`), so a track shorter than the episode is fine. A film
runs long enough for a loop to be heard: join the user's picks, in chapter order, into one bed
file at least as long as the film.

Bed level is one piecewise-linear `volume` envelope the renderer draws over the whole episode:
`bed_title_level` across the opening, then each shot's level by its cut-list `audio` mode
(`bed_level`: keep 0.10 / duck 0.20 / music-only 0.45) joined by `bed_ramp` ramps, falling to 0
across the end card. The shot's own gain comes from `shot_volume` (keep 1.0 / duck 0.6 /
music-only 0.3) with a `shot_edge_fade` on each edge so hard cuts do not click. Bed and shots meet
in a single `amix`, so changing a mode in the cut list moves both gains at once.

**Stamps.** `stamps.json` maps each beat card to a place name, or `null` for time of day alone.
Use evidence-backed names only — signage in frame, a leaflet, or the name said on camera — and ask
the user to fill the rest. Naming a place the footage cannot support is the one caption error
viewers who were there will catch.

**Captions.** `python scripts/build_subtitles.py --config <project>/series.json --transcripts
<review>/transcripts --out <project>/renders/subtitles --lang th` remaps source transcripts through
the cut into SRT sidecars — not burned in, so YouTube can translate them and the picture stays
clean. Fill the `subtitles` block of `series.json` first: the script the speech is written in,
the scripts that never occur in this footage, the Latin words that are real, and the series'
known ASR errors under `fixes`. A bad cue in the SRT is cured there and the SRT regenerated.

**Thumbnails.** `python scripts/build_thumbnails.py --config series.json --map thumbnails.json
--out <media>/final/thumbnails` draws a storyboard still plus the episode title through the same
renderer as the video, so the type matches exactly.

## 8. Draft and lock (gate)

Drafts are cheap: `--draft` is a half-canvas fast-preset render into `draft_output`
(default `<output>/draft`), ~4× realtime, so **every** episode gets one. Locking an unchanged
episode re-renders it at final settings (step 9); nothing about the draft is reused.

Present one checklist, so one reply settles everything:

1. the drafts to watch (paths, runtimes; loudness is normalized after QC, not now);
2. the bed per episode, with the candidate folder for audition;
3. the stamps table — beat, current label, the timestamp the beat starts (from
   `eNN.chapters.json`) — for correction;
4. the caption cues to check by ear (rough ASR runs, mid-word splits);
5. the thumbnails;
6. the teaser draft, if it exists.

Apply the answers: SRT and stamp text edits need no re-render — stamps are redrawn from
`stamps.json` on the next run. A bed or cut change re-renders that episode.

After lock, cuts, music, stamps and captions are fixed; everything later changes encoding only.
Say this back to the user when you report the lock, because steps 9–12 are long and "just one
shot" costs a render and, after upload, a re-upload.

Record the lock as a dated line in `BRIEF.md`.
