# Build — steps 6–9: proxies, compositions, music, stamps, captions, lock

## 6. Proxies

`python scripts/make_proxies.py --cut-lists <review>/clip-review --frame-index <review>/frame-index.json --source <source> --out <media>/clips-4k-g25 --size 4k --no-autorotate 0035,0064,0134,0141,0143,0146,0156`

One proxy per source file, spanning `min(in) − 1 s … max(out) + 1 s` across **every** use of that
file in the whole series, so a clip used by two episodes stays one file. `_ranges.json` records
each proxy's `offset`; a composition's `data-media-start` is then `source_time − offset`. Point
`<project>/assets/clips` at the proxy directory with a junction so compositions carry short
relative paths.

Encode flags that matter, and why:

- **`-g 25 -keyint_min 25 -bf 0`** — a keyframe every second. NVENC's default 10 s keyframe
  interval makes the HyperFrames compiler warn `sparse keyframes … causes seek failures and frame
  freezing`, and that warning is real. Treat it as a stop signal: fix the proxy, then render.
  Verify with `ffprobe -select_streams v:0 -show_entries frame=key_frame -read_intervals "%+#60"`
  and expect ≥2 keyframes in the first 60 frames.
- **`-noautorotate -display_rotation 0`** on the clips whose rotation tag was wrong (step 1).
  Fixing it in the proxy means the composition, the stills and the teaser all agree.
- **Scale + pad to the target canvas, `setsar=1`, constant `-r`**, so every proxy is already the
  render geometry and the page does no scaling work.
- NVENC first, `libx264 -crf 20` as the automatic fallback: a handful of clips reject the GPU path.

Cut proxies at the **final** resolution. A 1080p proxy set cannot produce a 4K final, and the
re-cut costs an hour.

**Per-shot proxies** (`scripts/make_shot_proxies.py`, dry-run by default) cut one file per shot
over `in − 1 s … out + 1 s`, so every `data-media-start` is ~1 s. Reach for them when one episode
holds many long proxies with deep seeks — they shrink the page's media footprint from gigabytes to
megabytes. They did **not** cure the capture stalls on their own (`reference/render.md`), so treat
them as page-weight relief rather than a stall fix.

## 7. Compositions

`python scripts/build_episodes.py --config series.json` writes one standalone composition per
episode into `compositions/episodes/eNN.html`. Generated files: change the generator and rerun
rather than editing HTML, so the cut list stays the single source of truth for timing.

Load `/hyperframes` before touching the generator; it owns the `data-start` / `data-duration` /
`data-media-start` contract, the `class="clip"` and `window.__timelines` registration rules, and
what makes a composition deterministic under seek. This skill only adds the series conventions:

- Each shot emits a muted `<video>` on track 0 plus a matching `<audio>` on an alternating track,
  both pointing at the same proxy, so the picture and its original sound stay locked together.
- A 0.12 s fade on each audio edge (capped at a third of the shot) keeps hard cuts from clicking.
- A title card only over the first shot, place stamps from beat 2 onward, an end card carrying the
  music credit.
- Straight cuts throughout. A diary series earns nothing from transitions.

Validate with `hyperframes check` and compare each composition's `data-duration` against its cut
list's `episode_seconds`.

**Text layers.** Fonts are bundled under a private family name with a local `@font-face` and no
generic fallback in the stack — naming `Georgia` or `serif` makes the compiler fetch a Google face
at render time. A scrim or gradient sharing a container with text gets the text lines
`position: relative; z-index: 1`: an absolutely positioned scrim paints **over** static text and
dims it to ~55%, and the contrast audit still passes. The luminance check in `reference/qc.md`
is what catches it.

**CLI notes.** `snapshot -o <dir>` empties `<dir>` first — point it at scratch and copy out.
`render` has no `--no-proxy`; proxying is `hyperframes.json`'s `media.autoProxy`. Font weights
come from the upstream variable file via `fontTools.varLib.instancer` (`wght=400`), same OFL.

## 8. Music, stamps, captions, thumbnails

**Music.** One bed per episode, chosen by the user from candidates you source. Each series
gets its own beds: reusing a previous series' tracks reads as the same video and was rejected on
sight. Procedure: load `/media-use` and `resolve` two or three cleared candidates per slot (CC BY,
CC0 or a catalogue with a ledger record; the licence must cover every platform the series goes
to), frozen under `<project>/assets/bgm-candidates/<slot>/` with a `CANDIDATES.md` (title,
artist, source, licence, exact credit line, duration, why it fits). Give the user the folder path
to audition and wait for one name per slot. Then loop the pick past the longest episode,
`loudnorm I=-20 LUFS`, AAC into `assets/bgm/`, write `CREDITS.txt` naming every track, and set
`bed` and `text.credit` in `series.json`. Bed level follows the per-shot `audio` mode through a
`data-automation` volume lane with ~0.6 s ramps, sitting at title level over the opening and fading
to zero over the end card. Load `/hyperframes-audio` for the automation and ducking semantics.

**Stamps.** `stamps.json` maps each beat card to a place name, or `null` for time-of-day only.
Use evidence-backed names only — signage in frame, a leaflet, or the name said on camera — and ask
the user to fill the rest. Naming a place the footage cannot support is the one caption error
viewers who were there will catch. Rendered as a thin rule above mono letter-spaced text, no
background block. Time of day derives from the filename hour.

**Captions.** `python scripts/build_subtitles.py --cut-lists <review>/clip-review --transcripts <review>/transcripts --out <project>/renders/subtitles --lang th`
remaps source transcripts through the cut into SRT sidecars — not burned in, so YouTube can
translate them and the picture stays clean. It drops `no_speech_prob > 0.6` segments and
degenerate repeats, applies a known-ASR-error fix list (`--fix "wrong=>right"`), splits cues over
6 s on word timestamps, merges sub-0.7 s cues, and enforces a 1 s minimum with no overlap.

**Thumbnails.** `python scripts/build_thumbnails.py --config series.json --map thumbnails.json`
renders each thumbnail through a HyperFrames `snapshot` of a 1280×720 composition rather than
drawing text with an image library, so the thumbnail's type matches the video's exactly.

## 9. Lock (gate)

The drafts are the finals-to-be: render every beat-range part at final settings (`--resolution`
cannot be smaller than the canvas, so a 4K series has no cheap 1080p draft), join, and hand the
joined files over. Present one checklist, so one reply settles everything:

1. the joined episodes to watch (paths, runtimes; loudness is normalized after the lock);
2. the bed per episode, with the candidate folder for audition;
3. the stamps table — beat, current label — for correction, with the timestamp each beat starts;
4. the caption cues to check by ear (rough ASR runs, mid-word splits);
5. the thumbnails;
6. the teaser draft, if it exists.

Apply the answers: SRT text and stamp edits need no re-render; a bed or cut change re-renders the
affected parts (a bed change re-renders every part of that episode, since each part carries a
slice of the bed). Move the superseded renders aside before relaunching the batch
(`reference/render.md`). After lock, cuts, music, stamps and captions are fixed; everything later
changes encoding only. Say this back to the user when you report the lock, because steps 10–13
are long and "just one shot" costs a part render and, after upload, a re-upload.

Record the lock as a dated line in `BRIEF.md`.
