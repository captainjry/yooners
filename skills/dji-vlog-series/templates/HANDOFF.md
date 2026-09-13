# HANDOFF — <what the next session takes over>

Write one of these whenever a render batch outlives the session. Keep it short enough that the
next session reads all of it, and put every path in absolute form.

Written `<date time>` by `<session>`.

## The next session's job, in order

1. <first task, with its completion criterion>
2. <second task>
3. Report per episode: done and verified, or the exact failure line.

<State plainly what is locked: "Everything editorial is approved and locked (cuts, music, stamps,
subtitles, thumbnails, upload sheet)." A handoff that omits this invites a re-edit.>

## Where the truth lives (read these rather than re-deriving)

- Project root: `<project>` — `BRIEF.md` (decision log at the bottom).
- Render driver: `<project>/tools/render_batch.sh` — idempotent, one render at a time, per-episode logs.
- Logs: `<review>/render-batch.log` (one START/DONE/FAILED line per item) and
  `<review>/render-eNN.log` (`grep 'Failure summary'` gives the stage and error).
- Finals: `<media>/final/` — `<Series>-ENN.mp4`, `YOUTUBE.txt`, `thumbnails/`, `qc/`.
- Proxies: `<project>/assets/clips` is a junction to `<media>/<proxy set>`.

## State at handoff

| Item | Rendered | Joined | QC | Normalized | Uploaded |
|---|---|---|---|---|---|
| E01 part1 (beats 1–3, N frames) | yes, 1.9 GB | — | — | — | — |
| E01 part2 (beats 4–6, N frames) | rendering since hh:mm | — | — | — | — |
| E01 joined (N frames, S s) | — | no | no | no | no |
| Teaser | draft only | n/a | no | no | no |

Confirm this table first: list the finals, then check the process list for live renders. A
`.hf-transaction-*` directory means a render is in progress or died; clear it only when no render
process is alive. When the user paused mid-batch, say which part was rendering and that the batch
command below resumes from it. To stop a live render, follow `reference/render.md` § Process
hygiene (by PID, in order).

## Commands, verbatim

<The exact render, join, QC and normalize commands with their arguments (frame totals and seam
frames for each episode). Say "copy, do not improvise" — every flag in it was learned from a
failure.>

## Open editorial items

<Anything the lock left to the user: a bed still to pick, caption cues awaiting a native speaker.
SRT and stamp edits need no re-render; say so.>

## Known failure modes and what fixed them

<Carry the live ones forward from reference/render.md, with the frames or errors observed in THIS
project. Drop the ones that no longer apply.>

## Do not

- Reopen any locked creative decision.
- Write to `<source>`.
- Run QC, decode sweeps, thumbnails, or a preview while a render is in progress.

## Suggested skills

- `dji-vlog-series` — the workflow this handoff sits inside.
- `hyperframes-cli` — only if a render fails in a way the logs leave unexplained.
