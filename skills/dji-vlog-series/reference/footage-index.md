# Footage index — steps 1–3

Everything here is read-only on `<source>`. Outputs land in `<review>`.

## 1. Metadata scan

`python scripts/scan_footage.py --source <source> --out <review> --metadata-only`

Writes `source-metadata.json`: one object per file with `streams[]` (codec, width, height,
color_space/transfer/primaries, avg_frame_rate) per stream.

What to settle from it before moving on, because each one changes later steps:

- **Which files are the series.** Camera filenames carry the shooting clock
  (`DJI_YYYYMMDDhhmmss_NNNN_D.MP4`), and a card usually holds several shoots. Count the files per
  date prefix and ask the user which prefixes belong to this trip before scanning — an adjacent
  shoot two weeks earlier may be the same trip or a different series. Confirm the mapping to
  calendar days with the user rather than inventing Day 1–N from the camera clock, which drifts
  and lies across time zones.
- **Odd files.** A short static clip at the head of the range is usually a desk/camera test.
- **Frame rate and codec.** Mixed rates (a few 29.97 clips in a 23.976 set) are conformed to the
  project fps by the proxy step's constant `-r`; list the odd clips so the proxy report can confirm
  it. HEVC sources decode slowly, which is the whole reason for proxies (step 6).
- **Rotation tags.** Some clips carry a `-90` display rotation over landscape content. Collect
  those clip numbers now; the proxy step zeroes them (`reference/build.md`).
- **Total raw seconds per day.** This is the honest ceiling on each episode's runtime. A day with
  321 s of raw footage yields a short episode, not a padded one.

## 2. Visual index and contact sheets

`python scripts/scan_footage.py --source <source> --out <review>`

Writes:

- `thumbnails/<stem>-{0,1,2}.jpg` — three frames per clip at 15%/50%/85% of its duration.
- `frame-index.json` — `[{file, duration, frames:[{seconds, path}]}]`. Later steps read
  `duration` from here, so it must cover every clip.
- `sheets/sheet-NN.jpg` + `sheet-manifest.json` — six clips per sheet (one row per clip, frames
  left to right), so ~28 sheets for 168 clips. Tiles carry no labels: map rows to filenames through
  the manifest's `files` order. **Read every sheet as an image.** The index is worth nothing if
  the frames were never seen.

Then write `complete-visual-index.json` yourself from what you saw:

```json
{"coverage": "<how the footage was sampled, in one sentence>",
 "clips": [{"file": "DJI_....MP4", "scene": "Desk beneath monitor; cables, watch.",
            "priority": "anchor|support|omit", "human": "No people visible.",
            "sample": 1, "note": "2.135s. Static equipment view; no trip action.",
            "privacy": null}]}
```

`privacy` names anything in frame that must not be published or must be trimmed around: a Wi-Fi
password card, a licence plate, a boarding pass, a form being filled in. The cut-list workers and
the crop step read it; such a card is easy to miss.

`coverage` states the sampling honestly — three frames per clip is coverage, not viewing. Keep
that caveat alive: shots chosen from stills get re-checked in motion at step 5 via the transcript.
`priority` drives selection: `anchor` carries a beat, `support` is connective texture, `omit`
needs a transcript reason to be used at all.

## 3. Transcription

`python scripts/transcribe_all.py --source <source> --out <review>/transcripts`

faster-whisper `large-v3` on CUDA, `vad_filter`, `word_timestamps`, `beam_size 5`,
`condition_on_previous_text=False` (a travel vlog has no continuous narrative; conditioning
carries hallucinated text between unrelated clips). Audio is extracted to a temp mono 16 kHz WAV
per clip and thrown away.

Per clip it writes `<stem>.json`:

```json
{"file": "...", "summary": {"language": "th", "language_prob": 0.99, "duration": 61.2,
 "speech_seconds": 22.4, "segments": 14, "preview": "..."},
 "segments": [{"start": 0.5, "end": 3.1, "text": "...", "no_speech_prob": 0.04,
               "words": [{"w": "...", "s": 0.5, "e": 0.8}]}]}
```

plus `transcripts/_index.json` mapping file → summary, rewritten after each clip so a crash
resumes cleanly (the script skips clips whose JSON already exists).

The transcript is what turns a visual index into an editorial one: it is the only evidence for
who said what, so it decides which shots carry a beat, and its word timestamps drive both the
cut in/out points and the subtitle sidecars. Two fields matter downstream:
`no_speech_prob > 0.6` marks a segment as unreliable, and degenerate repeats (four-plus tokens
with two or fewer distinct) are ASR hallucinations. Both get filtered at steps 5 and 8.

Expect three hallucination shapes on silent or windy clips and keep a per-series fix list for the
subtitle build (`--fix "text=>"` deletes a cue): stock filler in the wrong language ("Thank you.",
"All right.", "selamat menikmati"); a stray-language line with a *low* `no_speech_prob`, which the
threshold will not catch; and invented names or destinations under a public-address announcement.
Quote none of them in a cut list. A clip that is real speech but not the vlog's language (an
airport PA) keeps its audio and gets no caption.

Order the queue so the clips that answer an open question transcribe first — the last day's
footage settles how the series ends.
