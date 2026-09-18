# Render — step 9

One episode per invocation, one ffmpeg graph, straight from the proxies:

```
python scripts/build_episodes.py --config series.json 04          # final 4K
python scripts/build_episodes.py --config series.json 04 --draft  # 1080p proof
```

Every path comes from `series.json`; the only arguments are the episode number and the flags.
`--help` lists them all — the ones that carry a decision:

- **`--draft`** halves the canvas and drops to a fast preset, into `draft_output`. Use it for the
  lock gate (step 8) and for any graph change you want to see before paying for a final.
- **`--force`** re-renders over an existing output. Without it an episode whose final exists is
  skipped, so a relaunch resumes a series where it stopped.
- **`--cpu`** swaps NVENC for `libx264` on a machine with no usable GPU. Final NVENC is
  `-preset p6 -tune hq -cq 19`.
- **`--beats 2-3`** renders one beat range to its own file, for looking at a fix without the
  episode around it. Not how a final is produced.
- **`--dry-run`** writes `eNN.cmd.txt` and `eNN.filter.txt` and stops — the graph to read when you
  are asking what the renderer will actually do.

## The split

Over `--split` shots (default 10) the picture renders in beat-range parts at **final** settings
into `<out>/parts/`, and the sound is mixed in one pass over the whole episode; the join is
`ffmpeg -f concat -c copy` with the audio muxed in. Automatic, frame-exact, and the bed has no
seam because it was never cut. No user action, no separate join command.

The split exists because ffmpeg reads ahead on every open input — about 0.5 GB per 4K shot — so a
single graph over a long episode grows past what the machine has.

Measured on a synthetic 4K fixture, RTX 3060: final 4K ≈ 1.9× realtime (≈2.7 min for a 5-minute
episode), peak RSS ≈ 6 GB at the default split; 1080p draft ≈ 4× realtime.

## Reading the run

Progress prints every ~10 s with frames, fps, speed, ETA and peak RSS. Per episode the run writes
`eNN.log` (the ffmpeg stderr) and `eNN.chapters.json` — `[{card, start_seconds, stamp}]` plus
`total_seconds` and `frames` — which is what steps 10 and 11 read for expected duration, expected
frame count and chapter timestamps.

The last line is an ffprobe check of the container's packet count against the frame count the
plan computed:

- **PASS** — frame-exact; hand it to QC.
- **FAIL** — the file is short or long. Read `eNN.log`, fix the cause, re-render with `--force`.
  Do not patch a FAIL file.

A non-zero ffmpeg exit prints the last 12 log lines and stops the run.

## Re-rendering after a lock change

Re-render only the episodes that changed, either with `--force` or by moving the old final into
`<final>/superseded-<date>/` first — keep it until the new one passes QC. Stamp text changes are
picked up automatically: the layer PNGs are redrawn on every run.

## Self-test

The renderer can be proved end to end in under a minute, with no real footage:

```
python scripts/make_fixture.py --out <dir> --fonts <project>/assets/fonts
python scripts/build_episodes.py --config <dir>/series.json --draft
```

It must print PASS. Run it after changing the graph, or on a new machine before trusting a first
real render.

## Process hygiene

- **Stop a render by PID, never by image name.** Claude Code runs on node and the machine may hold
  other ffmpeg work. List the render's own processes by command line, then kill the Python driver
  and its ffmpeg child:
  `Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'build_episodes|ffmpeg' } | Select ProcessId, ParentProcessId, Name, CommandLine`
  then `Stop-Process -Id <pid>`. A part that dies half-written is re-rendered by the next run only
  under `--force`; delete it first otherwise.
- **Keep other heavy ffmpeg off the machine while a final renders.** It costs speed, not
  correctness — a QC sweep alongside a render finishes both, slower.

## Known limitation

In split mode a stamp on a beat shorter than `stamp_hold` is clipped at the part boundary. Either
give the beat more shots or accept the shorter stamp.
