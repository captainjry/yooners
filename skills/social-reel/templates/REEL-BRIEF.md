# <Series> — reel brief

Written <date>. Footage source: `<series project or folder>`. Reel project: `<this folder>`.

## Intake
- Reference: <URL or "described: ...">
- Footage: <dji-vlog-series project path | bare folder>
- Audio mode: <bed (bed: ...) | silent (platform sound: name, id; saved in-app on <date>)>

## Reference (from step 1)
Canvas, duration, N shots of a–b s, cut style, where people sit, text treatment, grade.
What the footage lacks vs the reference, and the stand-ins.

## Lockup
Lines (text, font, size, tracking), position (top | centre), colour, shadow. Font paths under
`design.fonts` in `reel.json` — serif only if the reference calls for it.

## Cut (draft gate — draft until locked)
Table from `cuts.json`: # | start | end | dur | file | in | shot | x_offset.
Not used: <candidates dropped and why>.

## Gates
1. Draft: `build_reel.py --draft`, watched by the user. Locked <date>.
2. Final: `build_reel.py`, watched by the user. Approved <date>.
Then QC, upload block appended to <upload sheet>.
