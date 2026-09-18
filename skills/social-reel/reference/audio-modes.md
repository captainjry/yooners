# Audio modes

Chosen at intake; it decides `reel.json`'s `audio` block and nothing else. `build_reel.py` reads
`audio.mode` directly — `"bed"` or `"silent"`.

| concern | `bed` | `silent` |
|---|---|---|
| timing source | BPM grid from `dji-vlog-series/scripts/measure_bpm.py --audio <bed>`; one bar per shot | hit map + the reference's cut points (`reference-reel.md`) |
| render | `audio.bed` mixed in, trimmed to the reel's length, `fade_out` seconds at the tail | `audio.mode: "silent"` — no audio stream in the file at all |
| loudness | check to −20 LUFS after render | none |
| credit | in the description | none; the platform credits the sound when attached |
| upload block | title, description with credit and licence URL, tags | file, the sound's name and id, "attach at 0:00, do not trim the head", caption, tags |

## Bed

Cleared beds only (CC BY with a `CREDITS.txt` beside them, or licensed). The cut grid: beat period
from the measured BPM, downbeat phase from the sub-180 Hz profile, every cut on a downbeat snapped
to the frame line — that grid is what fills `cuts.json`'s `in`/`out` pairs. Hook first, longest or
strongest shot on the section change.

`reel.json`: `{"audio": {"mode": "bed", "bed": "<path>", "gain": 1.0, "fade_out": 1.0}}`.

## Silent

The sound never touches disk. `build_reel.py` writes the file with `-an` — `ffprobe` on the output
shows zero audio streams, checked explicitly at QC. Keep the render at or under the sound's length.

Ask the user to **save the sound** in the app before the draft gate so it is in their saved list
at upload. Offer "Use audio" from the reference reel as the route.

The listening check happens in the platform's own editor, by the user: nobody hears the cut with
the sound before that. Say so in the report, name the two cuts to scrub to (the first cut and the
longest shot), and offer a two-minute re-render if a cut feels early or late.

Silent mode is the only legal path to a sound heard on another creator's reel — the sound is
attached in the platform's own picker at upload, never downloaded or re-encoded into the file.

Upload block shape:

```
REEL · <name>   (runtime 0:19, 1080x1920, SILENT file — attach audio in the app)
File: <final path>   (<dur> s, <frames> frames @ <fps>, no audio stream)
Post as a Reel. Add audio -> Saved -> "<sound name>" (id <id>). Start 0:00; do not trim the head.
Cuts are timed to that sound from 0:00. Check the waveform against the first cut at <t> before posting.
[CAPTION] ... (+ translated alternative)   [NOTES] no music credit needed; not a YouTube Short as-is.
```
