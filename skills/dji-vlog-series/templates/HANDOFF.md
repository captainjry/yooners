# HANDOFF — <what the next session takes over>

Write one of these whenever renders outlive the session. Keep it short enough that the next
session reads all of it, and put every path in absolute form.

Written `<date time>` by `<session>`.

## The next session's job, in order

1. <first task, with its completion criterion>
2. <second task>
3. Report per episode: done and verified, or the exact failure line.

<State plainly what is locked: "Everything editorial is approved and locked (cuts, music, stamps,
subtitles, thumbnails, upload sheet)." A handoff that omits this invites a re-edit.>

## Where the truth lives (read these rather than re-deriving)

- Project root: `<project>` — `BRIEF.md` (decision log at the bottom), `series.json` (every path
  and every design value the render reads).
- Cut lists: `<review>/clip-review/eNN.json` — the single source of timing.
- Per-episode render output: `<media>/final/eNN.log` (ffmpeg stderr) and `<media>/final/eNN.chapters.json`
  (expected frames, total seconds, chapter starts).
- Finals: `<media>/final/` — `<Series>-ENN.mp4`, `YOUTUBE.txt`, `thumbnails/`, `qc/`.
  Drafts: `<media>/final/draft/`.
- Proxies: `<media>/<proxy set>/` with `_ranges.json` (also named in `series.json`).

## State at handoff

| Item | Draft | Final | QC | Normalized | Uploaded |
|---|---|---|---|---|---|
| E01 (N frames, S s) | yes | yes, 1.9 GB, PASS | yes | yes | no |
| E02 (N frames, S s) | yes | rendering since hh:mm | no | no | no |
| E03 (N frames, S s) | yes | no | no | no | no |
| Teaser | draft only | no | no | no | no |

Confirm this table first: list `<media>/final/`, then check the process list for a live
`build_episodes.py`. A render is idempotent — re-running skips an episode whose final exists — so
the command below resumes the series wherever it stopped. A final that exists but never printed
PASS is the one case to delete before re-running. To stop a live render, follow
`reference/render.md` § Process hygiene (by PID).

## Commands, verbatim

```
python <skill>/scripts/build_episodes.py --config <project>/series.json 02
python <skill>/scripts/build_episodes.py --config <project>/series.json 03
```

<One line per remaining episode, plus the QC and normalize commands with each episode's expected
duration from its chapters.json. Copy, do not improvise.>

## Open editorial items

<Anything the lock left to the user: a bed still to pick, caption cues awaiting a native speaker.
SRT and stamp edits need no re-render; say so.>

## Known failure modes and what fixed them

<Carry the live ones forward from reference/render.md, with the errors observed in THIS project.
Drop the ones that no longer apply.>

## Do not

- Reopen any locked creative decision.
- Write to `<source>`.

## Suggested skills

- `dji-vlog-series` — the workflow this handoff sits inside.
