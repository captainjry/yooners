# Storyboard and cut lists — steps 4–5

## 4. Beat strip (gate)

The unit is the **beat**: one card, one place-or-moment, one stamp, and — decisively — a hard cut
at each boundary. Beats are what the renderer splits a long episode on, so choosing them well now keeps the
split on hard cuts.

Shape the strip:

- 3–6 beats per episode, in the shape open-on-people → middle beats → close. Faces first; a
  landscape opener reads as stock footage.
- One card per beat, each carrying: episode, title, beat position, scene sentence, the raw
  seconds available, 2–3 `source_samples` (`<file> @ <seconds>`), and an audio note.
- Every still is a real extraction from the originals at a stated timestamp, logged in
  `storyboard-provenance.json`. Skip clips with wrong rotation tags rather than rotating them for
  the board — a rotated still misrepresents what the shot will look like.
- Runtimes come from raw seconds per day, not from a house target. Where footage cannot sustain
  the target, propose the honest shorter number and say why. Padding, looping and slow motion to
  hit a minimum all read as filler in a diary series.

The episode split was settled at intake (`reference/intake.md`, round 2): one episode per
meaningful day, outbound travel folded into episode 1 and the return into the last.

**A film** is one `proposed_episodes` entry, `"01"`, whose beats run the whole trip. Group them
into **chapters** (a day, or a place, as intake settled): each chapter keeps the 3–6 beat shape,
the film opens on people in its first chapter and closes in its last. Name each card
`e01-<n>-<chapter>-<moment>` so the chapter reads off the card; the beats become the YouTube
chapters.

## Presenting the board

Write `storyboard-plan.json` by hand (top level: `series`, `message`, `audience`, `arc`,
`date_labels` for the strip header; then `proposed_episodes[] → beats[] → source_samples[]`; see
the schema in the script docstring), then:

`python scripts/build_storyboard.py --plan <review>/storyboard/storyboard-plan.json --source <source> --out <review>/storyboard`

It extracts one still per `source_sample` from the read-only originals, logs every extraction in
`storyboard-provenance.json`, writes one `eNN-cards.md` per episode, and renders a single
self-contained `strip.html` with the stills embedded.

Give the user the `strip.html` path to open in a browser, **and** present the cards in the reply
one by one (episode, beat, title, one-line scene, stamp candidate). Feedback comes back in chat:
apply it, rebuild the strip, and present the changed cards again. Record the approval in
`BRIEF.md`. Retired cards move to `retired-cards/` instead of being deleted — they are the record
of what was considered, and the user may pull one back.

The gate is editorial approval of the strip. Steps 5–8 build exactly this strip.

## 5. Cut lists

One subagent per episode, dispatched in parallel, each with `templates/cut-list-worker.md` plus
its episode's cards. For a film, dispatch one worker per chapter with that chapter's cards; each
returns its `beats`, `human_audio_moments`, `captions_candidates` and `flags`, and you join them
in strip order into the one `e01.json`, summing `episode_seconds`, before the check below. A capable mid-tier model does this well; the judgement is bounded by the
approved cards.

Each worker writes `<review>/clip-review/eNN.json`:

```json
{"episode": "01", "target_runtime_s": 450,
 "beats": [{"card": "e01-1-travel-in",
            "shots": [{"file": "DJI_....MP4", "in": 12.4, "out": 18.9,
                       "why": "clear line: <gist>", "audio": "keep|duck|music-only",
                       "quote": "verbatim if kept", "lang": "th"}],
            "beat_seconds": 62}],
 "episode_seconds": 448,
 "human_audio_moments": [{"file": "...", "at": 33.2, "gist": "...", "strength": "strong|usable|weak"}],
 "captions_candidates": [{"file": "...", "in": 0, "out": 0, "text": "...", "translation": "..."}],
 "flags": ["anything the editor must check by watching"]}
```

Every downstream tool reads this file: proxies take their ranges from it, the renderer takes its
timing, subtitles take their shot windows, and the teaser lifts in-points from it. Times are
seconds from clip start at 1× in the **original** file — the proxy offset is applied later, once,
in one place.

`audio` is the per-shot mode and drives two gains at step 9: the shot's own volume
(`keep 1.0 / duck 0.6 / music-only 0.3`) and the music bed underneath it
(`keep 0.10 / duck 0.20 / music-only 0.45`).

`human_audio_moments[].strength` is the field that pays off twice: it ranks the real reactions
for the episode cut, and at step 12 the `strong` entries are the teaser's shot list.

Check each returned JSON before accepting it with
`python scripts/check_cut_list.py NN --review <review> --plan <review>/storyboard/storyboard-plan.json --target <s>`:
beat order against the approved strip, every `file` in `frame-index.json`, every `out` inside its
clip, beat and episode sums, runtime within 10 % of target. Then **frame-verify** the anchor
shots: extract the frame at each `in` and confirm the moment the `why` describes is on screen.
Text-only picks put the wrong thing in frame in a quarter of cases; move the in-point inside the
clip first, swap the clip second. A worker's flag that contradicts a premise you gave it deserves
the same frame check — such a flag can be right, for example by reinstating a
to-camera opening.

