---
name: dji-vlog-series
description: >
  Turn a folder of raw camera clips (DJI, phone, action cam) into a multi-episode travel-vlog
  series plus its vertical teaser. Use to plan, cut, render, QC, or re-render such a series:
  footage indexing, per-episode cut lists, proxies, ffmpeg episode renders with Pillow text
  layers, contact-sheet and loudness QC, and the YouTube upload sheet.
---

# DJI vlog series

Take a card of raw clips to N finished episodes and one teaser. Proven on 168 clips (3.1 h) →
ten 4K episodes + a 39 s short, and on 89 clips (29 min) → two 4K episodes + a 20 s reel.

The toolchain is ffmpeg, ffprobe, Python (Pillow, faster-whisper) and a POSIX shell. A diary
series is straight cuts, a title card, place stamps, an end card and a music bed; every one of
those is an ffmpeg filter or a PNG drawn by `scripts/textlayers.py`. No browser, no compositor.

`scripts/` holds the tools; every path is an argument or lives in `series.json`. Copy
`templates/series.json` into the project root and fill it before step 6.

**Placeholders**: `<project>` = the project dir (config, layers, fonts, music), `<review>` = the
sibling working dir holding indexes and logs, `<media>` = the scratch drive for proxies and
finals, `<source>` = the read-only originals.

## Steps

Work top to bottom. Two human gates (steps 4 and 8) stop the run until the user answers.

1. **Intake and metadata scan.** Ask which files on the card are the series (a card usually holds
   several shoots as filename-date prefixes), the trip name and slug, and the dates. Then ffprobe
   every source file into `source-metadata.json`; settle codec, fps, rotation tags, total runtime.
   *Done when* every source file appears in the JSON and the user has confirmed the prefix set,
   the name and the date range.
   → `reference/footage-index.md`, `scripts/scan_footage.py`

2. **Visual index and contact sheets.** Extract three frames per clip, tile them into sheets,
   and look at every sheet. Write one `complete-visual-index.json` row per clip: scene, human
   content, priority `anchor|support|omit`, and a `privacy` note for anything on screen that must
   not be published (passwords, plates, documents).
   *Done when* the index row count equals the clip count and each sheet has been viewed.
   → `reference/footage-index.md`, `scripts/scan_footage.py`

3. **Transcription.** faster-whisper `large-v3` locally, word timestamps, one JSON per clip.
   *Done when* `transcripts/_index.json` covers every clip and reports a language per clip.
   → `reference/footage-index.md`, `scripts/transcribe_all.py`

4. **Storyboard beat strip — gate.** One card per **beat** (3–6 beats per episode: open on
   people, middle beats, close), each backed by a real extracted still logged in
   `storyboard-provenance.json`. Propose honest runtimes from raw seconds per day. The strip is
   one self-contained `strip.html`; present it and the cards in the reply, card by card.
   *Done when* the user approves the strip card by card; retired cards move to `retired-cards/`.
   → `reference/storyboard-and-cuts.md`, `scripts/build_storyboard.py`

5. **Cut lists.** Dispatch one subagent per episode with the worker brief; each writes
   `clip-review/eNN.json` (beats → shots with in/out/why/audio/quote). Validate each with
   `scripts/check_cut_list.py`, then frame-verify the anchor shots.
   *Done when* every episode's list passes the validator and its `flags` list is empty or
   explained.
   → `reference/storyboard-and-cuts.md`, `templates/cut-list-worker.md`

6. **Proxies.** Cut proxies of only the used ranges at the **final** geometry and fps, rotation
   zeroed on wrongly-tagged clips. The proxy exists so every later ffmpeg pass reads one cheap,
   uniform H.264 file instead of seeking into HEVC originals.
   *Done when* every proxy probes at the target geometry and constant fps, and `_ranges.json`
   lists every clip the cut lists use.
   → `reference/build.md`, `scripts/make_proxies.py`

7. **Music, stamps, captions, thumbnails.** Fetch the fonts once; source cleared bed candidates
   per episode and let the user pick; write evidence-backed place **stamps**; build subtitle
   sidecars; draw thumbnails with the same text renderer as the video.
   *Done when* each episode has a user-chosen bed, every beat has a stamp or a deliberate `null`,
   each episode has an SRT and a thumbnail, and the music credit sits on the end card.
   → `reference/build.md`, `scripts/build_subtitles.py`, `scripts/build_thumbnails.py`

8. **Draft and lock — gate.** Render every episode as a half-canvas draft (1080p from a 4K
   series, minutes each) and present
   the lock checklist: the drafts to watch, the bed per episode, the stamps table, the caption
   cues to check by ear, the thumbnails.
   *Done when* the user says locked; from here on only encoding changes.
   → `reference/build.md`, `scripts/build_episodes.py`

9. **Render.** One builder run per episode at final settings from the proxies, straight to the
   finals dir; a long episode splits into beat-range parts and rejoins itself. After lock changes,
   re-render only the episodes that changed.
   *Done when* every final exists at the target geometry and the builder printed PASS for it.
   → `reference/render.md`, `scripts/build_episodes.py`

10. **QC.** Per final: geometry, duration, blackdetect, freezedetect, silencedetect, loudness,
    and a contact sheet you actually look at. Then normalize loudness to −20 LUFS.
    Hand each clean episode over as soon as it is clean — the user uploads one at a time.
    *Done when* the file passes every check and the sheet shows real, upright footage in every tile.
    → `reference/qc.md`, `scripts/qc_episode.sh`, `scripts/normalize_loudness.sh`

11. **Publish sheet.** Write `YOUTUBE.txt`: title, description with chapter timestamps, tags,
    music credit, subtitle and thumbnail paths, per episode.
    *Done when* every episode has all three blocks and the chapter times match the rendered file.
    → `reference/publish.md`

12. **Teaser.** Invoke `social-reel` with this project as the footage source (it reads the cut
    lists, `human_audio_moments` and the proxies directly) and the audio mode the user wants.
    *Done when* that skill reports the reel rendered and its upload block sits in `YOUTUBE.txt`.

## Standing rules

- Read the originals; write elsewhere. Every derived artefact lands in `<review>` or `<media>`.
- Report **rendered** and **uploaded** as separate columns; the user owns uploading.
- Generated files are regenerated, never hand-edited: the cut list is the single source of
  timing, `series.json` the single source of design and text.
- Keep a decision log at the bottom of `BRIEF.md`: one dated line per decision, newest last.
  It is the single source of truth for what happened across sessions.
  → `templates/BRIEF.md`
- Hand unfinished renders to the next session through a handoff file.
  → `templates/HANDOFF.md`
- Optional model routing, when the harness offers a choice: a mid-tier model for procedural steps
  (scans, proxies, renders, QC), a top-tier model for judgment steps (visual index, storyboard,
  cut lists), and the orchestrator stays in the main session.

## Known limitations

- `storyboard-plan.json` is authored by hand; `scripts/build_storyboard.py` turns it into stills,
  provenance, cards and the strip.
- Contact-sheet tiles carry no labels: rows map to clips through `sheet-manifest.json`, in order.
- Subtitle cues split on word timestamps can cut a word in two in scripts without spaces; a
  native speaker checks the SRT at the lock.
- Text layers are drawn with FreeType, so a series first designed in CSS keeps its design but not
  a bit-identical raster. Sizes in `series.json` are canvas pixels tuned at 4K; a 1080p series
  sets `text_scale` 0.5.
