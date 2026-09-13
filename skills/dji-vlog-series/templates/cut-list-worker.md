# Cut-list worker brief

Dispatch one subagent per episode with this brief plus that episode's approved storyboard cards.

---

You are reviewing source footage for ONE episode of `<series description>`. Your output is a cut
list the editor will assemble from. You do not edit video, do not touch originals, do not render.

## Ground truth you receive

- The episode's storyboard cards (approved by the user): beats, chosen stills, intent, audio notes.
- `complete-visual-index.json` entries for every clip in the episode's date range: scene, human
  content, priority (`anchor` / `support` / `omit`), best sample, notes, and `privacy` (anything
  in frame that must stay off screen: cut around it or leave the clip out, and say so in `flags`).
- `frame-index.json` durations and the sampled timestamps per clip.
- Word-level transcripts per clip in `transcripts/<clip>.json` (faster-whisper large-v3, local).
  Fields: `summary.language`, `summary.speech_seconds`,
  `segments[].start/end/text/no_speech_prob/words`. Speech may be in several languages; translate
  the gist in your notes. Segments with `no_speech_prob > 0.6` or hallucinated repetitions are
  unreliable: ignore them.

## What to produce

Write `clip-review/eNN.json` with this shape:

```json
{
  "episode": "01",
  "target_runtime_s": 450,
  "beats": [
    {
      "card": "e01-1-travel-in",
      "shots": [
        {"file": "<clip>.MP4", "in": 12.4, "out": 18.9, "why": "clear line: <gist>",
         "audio": "keep|duck|music-only", "quote": "verbatim if kept", "lang": "th"}
      ],
      "beat_seconds": 62
    }
  ],
  "episode_seconds": 448,
  "human_audio_moments": [{"file": "...", "at": 33.2, "gist": "...", "strength": "strong|usable|weak"}],
  "captions_candidates": [{"file": "...", "in": 0, "out": 0, "text": "...", "translation": "..."}],
  "flags": ["anything the editor must check by watching: possible fall, sideways rotation, dark shot, private info on screen"]
}
```

## Rules

- The approved cards decide which beats exist and their order. You choose the shots and in/out
  points within each beat, favouring the card's sample stills but free to pick better moments the
  transcript reveals.
- Faces and real exchanges first; scenery as short connective texture (2 to 5 s). Keep food inserts
  and panoramas from outweighing people.
- Shot lengths: most 2 to 8 s; a kept conversation may run 10 to 25 s if intelligible.
- Sum to the episode's target runtime within about 10 percent. Where usable footage falls short,
  come in under and say so in `flags`, rather than padding.
- Claim laughter, a fall, singing, a toast or a farewell only where the transcript or the visual
  index supports it. Stills and silence support none of these.
- Keep barcodes, reception slips and personal documents to incidental screen time.
- Clips marked `omit` in the visual index need a transcript reason to be used.
- Timestamps are seconds from clip start, at 1x, in the original file.
- Mark each shot `"verified": true` when you looked at a thumbnail or still at that in-point, and
  `false` when the pick rests on index text alone; the editor frame-checks the `false` ones.
- Keep notes short: the JSON plus a five-line summary printed at the end.
