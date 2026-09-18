# Survey, cut, crop, lockup — steps 2–3

The reel reads from the **same proxies** as the footage project (a `dji-vlog-series` project's
`proxies/`, or `make_proxies.py` run on a bare folder) — no separate render-ready copy, no
project-of-its-own beyond `reel.json` and `cuts.json` sitting next to a `clips` or `proxies`
pointer.

## Survey

The worker reads the visual index, the cut lists (`human_audio_moments[].strength`, shot in/out)
and the thumbnails, and writes `SHOT-SURVEY.md`: 2× the slots needed, each with episode, clip,
proxy file, a 1.5–2.5 s window in **proxy time** (`proxy_t = original_t − offset` from
`_ranges.json`), one line of description, the subject's horizontal position, a day-arc tag, and
whether that position was read from a thumbnail (`verified`) or from index text (`inferred`).
It also lists what the reference shows that the footage lacks, with the nearest stand-in, so the
editor swaps by intent rather than by discovering the gap at the gate.

**Frame-verify before the cut grid.** For every shot that reaches `cuts.json`, extract the frame
at its in-point (`ffmpeg -ss <in> -i <proxy> -frames:v 1 -vf scale=480:-1`) and confirm two things:
the moment described is on screen, and the subject fits the crop. On one reel, three of
sixteen surveyed in-points showed something else: the animals entered 15 s later, the described
pose was in a different clip, and a described interior was a selfie for its first 20 s. Move the
in-point inside the same clip first; swap the clip second.

## Cut grid — `cuts.json`

`cuts.json` is the single source of timing: `{"shots": [{"file", "in", "out", "x_offset"?}, ...]}`,
ordered, in **source seconds**. `build_reel.py` derives every start/end from it — nothing else
carries timing.

- Bed mode: shots are downbeats, one bar per shot (2.4–3.2 s keeps a reel moving; two-bar shots
  stall it). Hook first, one moment per episode.
- Silent mode: shots are the reference's cut points nudged onto the nearest hit; the longest shot
  goes over the section change. 1.2–2.8 s, median ~1.6 s, hard cuts.
- Face count: count the shots that are a large selfie face. More than a third reads as a
  selfie roll; swap the weakest for a wide with the person small, an interior, or a place.

## Crop

Every shot is scaled to the canvas height keeping aspect, then cropped to the canvas width — a
9:16 canvas over 16:9 source keeps 31.6% of the source width. `x_offset` is that crop window's
shift from centred, **in source pixels**; omit it for a centred crop. Choose it from the shot's
in-point frame, then check the out-point frame too: a subject walking across the frame leaves a
static crop. Two people 40% of the frame apart cannot share one crop; pick one.

`scripts/crop_sheet.py --config reel.json --mode plan --out sheet.png` draws the kept window on
each in-point frame with the exact math `build_reel.py` renders with; look at it before spending
render time.

## Lockup

One static text lockup, 2–3 lines, present unmoved for the whole reel — no stamps, no per-shot
captions, no animation. Serif or mono per the reference; upper third or centre. In `reel.json`:

```json
"lockup": {
  "lines": [{"text": "TITLE", "font": "serif", "size": 84, "tracking": 2},
            {"text": "PLACE · DATE", "font": "mono", "size": 26, "tracking": 4}],
  "position": "top", "top_px": 220, "color": "#F5F1E8", "shadow": [0, 2, 18, 0.5]
}
```

`build_reel.py` renders it once with `dji-vlog-series/scripts/textlayers.py`'s `render_lockup`
and overlays the PNG for the render's full length.

Rules that held on every build:

- Fonts are the series' own TTFs (`design.fonts.sans` / `.mono` / optional `.serif`), the same
  ones `fetch_fonts.py` pulls for `dji-vlog-series` — no generic font-family fallback.
- White type over bright snow fails 3:1 without help: give the lockup a soft top-down scrim in the
  same shot, or drop a shadow into `lockup.shadow`. Verify with
  `scripts/text_luminance.py --video final.mp4 --at <t> --band x0,y0,x1,y1`: brightest pixel in
  the lockup band must read 255 for white type — a lower peak means the scrim or a blend is
  dimming it.
- Keep the bottom ~20% and the right edge clear; the platform UI sits there.

## Render

`scripts/build_reel.py --config reel.json --draft` is the gate render (half canvas, fast preset);
`scripts/build_reel.py --config reel.json` is the final (full canvas, NVENC unless `--cpu`). Both
read the same `reel.json` and `cuts.json` — nothing to keep in sync by hand. `--dry-run` writes
`.cmd.txt`/`.filter.txt` to read the graph without paying for a render. → `SKILL.md` step 4,
`scripts/build_reel.py`'s own docstring.
