---
name: social-reel
description: >
  Cut a vertical Reel, Short or TikTok (15–40 s) from existing footage in the style of a
  reference reel. Use when the user pastes a reel/short URL to copy, asks for a teaser or promo
  of a finished vlog series, or wants a montage from a folder of clips. Covers reference
  analysis in the browser, shot survey with frame-verified in-points, 9:16 crop, a static
  text lockup, and both audio modes: a bed embedded in the render, or a platform sound
  attached at upload with a silent render.
---

# Social reel

One vertical reel from footage that already exists: hard cuts on a hit map or BPM grid, a 9:16
cover-crop of 16:9 footage, one static text lockup that never moves, no animation.

The toolchain is ffmpeg, ffprobe and Python (Pillow) — the same one `dji-vlog-series` renders
episodes with. `scripts/build_reel.py` does the render; `scripts/` holds the rest.
`templates/cuts.json` and `templates/reel.json` are the two files every render reads.

**Requires:** the `dji-vlog-series` skill installed beside this one (its `scan_footage.py`,
`make_proxies.py`, `measure_bpm.py`, `fetch_fonts.py` and `textlayers.py` are called by path),
`ffmpeg`/`ffprobe` on PATH, Python 3 with Pillow, and for step 1 a Chrome the user is
logged into with the Claude browser extension. Paths in this skill are placeholders; the project's
own brief holds the real ones.

## Intake — settle three things before any work

1. **Reference.** A reel URL, or a style described in words. With a URL, step 1 measures it;
   without one, write the reference block of `templates/REEL-BRIEF.md` from the description.
2. **Footage source.** A `dji-vlog-series` project (read its visual index, cut lists,
   `human_audio_moments` and proxies directly) **or** a bare folder of clips (run
   that skill's `scan_footage.py` for an index and cut proxies of the used ranges with
   `make_proxies.py`; transcription is optional).
3. **Audio mode.** `bed` (a cleared bed mixed into the render) or `silent` (a sound in the
   platform's library, attached in the app; the render is silent). → `reference/audio-modes.md`.
   Silent mode is the only legal path to a sound heard on another creator's reel.

*Done when* the three answers are written at the top of `REEL-BRIEF.md` in the new project folder.

## Steps

1. **Measure the reference.** In the user's logged-in Chrome: canvas, duration, a 19-frame contact
   sheet, the picture cut points, and (silent mode) the sound's onset hit map — all in-page,
   nothing saved to disk. Write `AUDIO-MAP.md`.
   *Done when* the cut-point list and the hit map agree at offset 0, or the offset is stated.
   → `reference/reference-reel.md`, `scripts/reference_reel.js`

2. **Survey the shots.** One subagent lists 2× the needed shots with proxy-relative in/out, a
   subject-position call, and a day-arc tag. Every in-point is then **frame-verified**: extract
   the frame at the in-point and confirm it shows the moment the text describes. Text-only
   surveys put the wrong thing on screen in 4 of 16 picks.
   *Done when* `SHOT-SURVEY.md` marks each candidate `verified` or `inferred`, and every proxy
   named exists on disk.
   → `reference/cut-and-crop.md`

3. **Cut grid.** Fill `cuts.json` (shots in source seconds, `x_offset` per shot from the survey),
   write the `lockup` block of `reel.json` from the reference's text treatment, then run
   `scripts/crop_sheet.py --config reel.json --mode plan --out sheet.png` and look at it before
   spending render time.
   *Done when* the sheet shows every crop holding its subject and no shot needs a swap.
   → `reference/cut-and-crop.md`

4. **Draft render — gate.** `python scripts/build_reel.py --config reel.json --draft`
   (add `--cpu` on a machine with no usable GPU). Present the draft file, the cut table and the
   plan sheet; ask the user's calls on any flagged shot.
   *Done when* the user says lock. After lock, timing and shots change only on the user's word.

5. **Final render.** `python scripts/build_reel.py --config reel.json`. Then
   `scripts/crop_sheet.py --config reel.json --mode render --video <final> --out sheet.png` and
   `scripts/text_luminance.py --video <final> --at <t> --band <lockup band>`.
   *Done when* the render prints `PASS` on frame count and the luminance check reads 255.

6. **QC and upload block.** Geometry, frame count, blackdetect, freezedetect, the render sheet
   read by eye. Bed mode: loudness to −20 LUFS. Silent mode: confirm `ffprobe` shows zero audio
   streams. Append the block from `reference/audio-modes.md` to the series' upload sheet, or write
   `UPLOAD.md` for a bare folder.
   *Done when* the report shows rendered and uploaded as separate columns; the user uploads.

## Standing rules

- Two gates: the draft render (step 4), then the user watching the actual final. Never gate on
  an artifact or a screenshot — a draft is a real render the user can watch.
- Orchestrate: a mid-tier model surveys and builds; the cut and crop calls are the editor's.
- Read the footage project; write only in the reel's own folder plus an appended line in the
  series `BRIEF.md` decision log and the upload sheet.
- `build_reel.py` writes `<out>.cmd.txt` / `.filter.txt` / `.log` next to the output — read the
  filter script when a render doesn't look right before touching the graph.
- Stop a render by PID, never by image name — the agent itself runs on node.
- Names of people stay off screen.

## Self-test

`scripts/make_reel_fixture.py` proves the renderer end to end in under a minute, with no real
footage — run it after changing `build_reel.py` or `textlayers.py`'s `render_lockup`, or on a new
machine before trusting a first real render:

```
python scripts/make_reel_fixture.py --out <dir>
python scripts/build_reel.py --config <dir>/reel.json --draft   # must print PASS
python scripts/build_reel.py --config <dir>/reel.json            # must print PASS
```
