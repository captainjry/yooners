---
name: dji-vlog-series
description: >
  Turn a folder of raw camera clips (DJI, phone, action cam) into a multi-episode travel-vlog
  series plus its vertical teaser. Use to plan, cut, render, QC, or re-render such a series:
  footage indexing, per-episode cut lists, 4K proxies, beat-range part renders, contact-sheet
  and loudness QC, and the YouTube upload sheet.
---

# DJI vlog series

Take a card of raw clips to N finished episodes and one teaser. Proven on 168 clips (3.1 h) →
ten 4K episodes + a 39 s short, and on 89 clips (29 min) → two 4K episodes + a 20 s reel.

HyperFrames is the composition and render framework. This skill owns the **series** workflow;
composition and render semantics live in the HyperFrames skills. Load `/hyperframes` once at
step 7, and `/hyperframes-cli` when a render fails in a way the logs leave unexplained.

`scripts/` holds the tools; every path is an argument or lives in `series.json`. Copy
`templates/series.json` into the project root and fill it before step 6.

**Placeholders**: `<project>` = the HyperFrames project dir, `<review>` = the sibling working
dir holding indexes and logs, `<media>` = the scratch drive for proxies and finals,
`<source>` = the read-only originals.

## Steps

Work top to bottom. Two human gates (steps 4 and 9) stop the run until the user answers.

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
   `storyboard-provenance.json`. Propose honest runtimes from raw seconds per day. Cards are
   HyperFrames frame compositions listed in `STORYBOARD.md` and reviewed in the Studio preview's
   Storyboard view; the user's per-frame comments land in `.hyperframes/frame-comments.json`.
   *Done when* the user approves the strip card by card; retired cards move to `retired-cards/`.
   → `reference/storyboard-and-cuts.md`, `scripts/build_storyboard.py`

5. **Cut lists.** Dispatch one subagent per episode with the worker brief; each writes
   `clip-review/eNN.json` (beats → shots with in/out/why/audio/quote). Validate each with
   `scripts/check_cut_list.py`, then frame-verify the anchor shots.
   *Done when* every episode's list passes the validator and its `flags` list is empty or
   explained.
   → `reference/storyboard-and-cuts.md`, `templates/cut-list-worker.md`

6. **Proxies.** Cut render-ready proxies of only the used ranges at the **final** resolution,
   1 s keyframes, constant fps, rotation zeroed on wrongly-tagged clips.
   *Done when* every proxy probes clean and shows ≥2 keyframes in its first 60 frames.
   → `reference/build.md`, `scripts/make_proxies.py`

7. **Compositions.** Generate one composition per episode from the cut lists — never hand-edit;
   regenerate. Read `/hyperframes` for the `data-*` timing contract before changing the generator.
   *Done when* `hyperframes check` passes for every episode and each duration matches its cut list.
   → `reference/build.md`, `scripts/build_episodes.py`

8. **Music, stamps, captions, thumbnails.** Source cleared bed candidates per episode and let the
   user pick; write evidence-backed place **stamps**; build subtitle sidecars; build thumbnails
   through a HyperFrames snapshot so the fonts match the video.
   *Done when* each episode has a user-chosen bed, every beat has a stamp or a deliberate `null`,
   each episode has an SRT and a thumbnail, and the music credit sits on the end card.
   → `reference/build.md`, `scripts/build_subtitles.py`, `scripts/build_thumbnails.py`

9. **Lock — gate.** Render the beat-range parts at final settings, join, and present the lock
   checklist: the episodes to watch, the bed per episode, the stamps table, the caption cues to
   check by ear, the thumbnails. An unchanged lock makes these renders the finals.
   *Done when* the user says locked; from here on only encoding changes.
   → `reference/build.md`

10. **Render.** One render at a time, `--workers 1`, GPU, from the 1 s-keyframe proxies. Any
    episode over ~5500 frames renders as beat-range **parts** joined losslessly; after lock
    changes, re-render only what changed.
    *Done when* every final exists at the target geometry and every joined episode's video packet
    count equals its expected whole-episode frame count.
    → `reference/render.md`, `scripts/render_batch.sh`, `scripts/join_parts.sh`

11. **QC.** Per joined file: geometry, duration, blackdetect, freezedetect, silencedetect,
    loudness, and a contact sheet you actually look at. Then normalize loudness to −20 LUFS.
    Hand each clean episode over as soon as it is clean — the user uploads one at a time.
    *Done when* the file passes every check and the sheet shows real, upright footage in every tile.
    → `reference/qc.md`, `scripts/qc_episode.sh`, `scripts/normalize_loudness.sh`

12. **Publish sheet.** Write `YOUTUBE.txt`: title, description with chapter timestamps, tags,
    music credit, subtitle and thumbnail paths, per episode.
    *Done when* every episode has all three blocks and the chapter times match the rendered file.
    → `reference/publish.md`

13. **Teaser.** Invoke `social-reel` with this project as the footage source (it reads the cut
    lists, `human_audio_moments` and the proxies directly) and the audio mode the user wants.
    *Done when* that skill reports the reel rendered and its upload block sits in `YOUTUBE.txt`.

## Standing rules

- Read the originals; write elsewhere. Every derived artefact lands in `<review>` or `<media>`.
- Report **rendered** and **uploaded** as separate columns; the user owns uploading.
- Leave finals in place while a batch script runs — the script re-renders whatever is missing.
- Keep a decision log at the bottom of `BRIEF.md`: one dated line per decision, newest last.
  It is the single source of truth for what happened across sessions.
  → `templates/BRIEF.md`
- Hand a long-running render to the next session through a handoff file; stop a render only by
  PID.
  → `templates/HANDOFF.md`, `reference/render.md`
- Optional model routing, when the harness offers a choice: a mid-tier model for procedural steps
  (scans, proxies, renders, QC), a top-tier model for judgment steps (visual index, storyboard,
  cut lists, composition fixes), and the orchestrator stays in the main session.

## Known limitations

- `storyboard-plan.json` is authored by hand; `scripts/build_storyboard.py` turns it into stills,
  provenance, cards and the Studio storyboard.
- Contact-sheet tiles carry no labels: rows map to clips through `sheet-manifest.json`, in order.
- Subtitle cues split on word timestamps can cut a word in two in scripts without spaces; a
  native speaker checks the SRT at the lock.
- `scripts/scan_footage.py` reconstructs steps 1–2 from the output schemas rather than copying an
  original; check its first sheet before running the whole sweep.
