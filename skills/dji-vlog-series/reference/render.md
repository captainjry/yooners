# Render — step 10

Measured on HyperFrames 0.8.33, 4K, NVENC: ~0.19 s/frame, ~35 min per 7-minute episode.

## Flags

```
render -c compositions/episodes/eNN.html -q high --crf 18 --gpu --workers 1 \
       --resolution landscape-4k --player-ready-timeout 300000 -o <out>.mp4
env PRODUCER_STREAMING_ENCODE_MAX_DURATION_SECONDS=3600
    PRODUCER_PLAYER_READY_TIMEOUT_MS=300000 PRODUCER_RENDER_READY_TIMEOUT_MS=300000
    PRODUCER_PUPPETEER_PROTOCOL_TIMEOUT_MS=1800000
```

- **`--workers 1` is load-bearing**: streaming encode engages only with one worker. More workers
  dump raw frames to temp instead — about 344 GB per 4K episode.
- **`--gpu`** is the NVENC final encode. Capture stays CPU-bound either way.
- **`--resolution landscape-4k`** with 4K proxies. State it explicitly; the default is 1080p.
- **No downscaled drafts.** `--resolution` cannot be smaller than the composition canvas ("Downsampling via
  --resolution is not supported"). For a 4K series the lock-gate drafts are 4K renders at final settings, so
  an unchanged lock makes them the finals; a cheaper draft needs its own 1080p composition set.
- Keep `--gpu` on for the browser too. With `--no-browser-gpu` the stalls below arrive *earlier*.

## The length ceiling, and parts

Sequential streaming capture stalls on long episodes: `Sequential screenshot capture stalled: no
frame progress for 60000ms`. Observed on E04 five times at frames 2546–6608 across two different
proxy sets, and on E06 at 9057 of 10144. The capture rate is steady and then dead — different
frames each run, so it is the run length rather than any clip. Nothing under ~6100 frames ever
stalled.

So render any episode over ~5500 frames as **parts**:

```
python scripts/build_episodes.py --config series.json 04 --parts=1-2,3-4,5-6
```

Each part is a beat range, which means every split lands on a hard cut. The generator holds the
join together:

- Each part's offset is snapped **up** to the joined frame grid (`frames_rendered_so_far / fps`),
  so `sum(part frames) == whole-episode frames` with no duplicated or dropped frame.
- The music bed gets `data-media-start` = the part's absolute offset and a sliced copy of the
  whole-episode automation, so the bed is sample-continuous across the seam.
- The title card appears only in the part holding beat 1; the end card only in the last part.

Then `sh scripts/join_parts.sh 04 3 --total 10982 --seams 3868,6924` concatenates with
`ffmpeg -f concat -c copy` (no re-encode, bit-identical video) and checks the join:

1. video packet count equals the expected whole-episode frame count,
2. no `Non-monotonous DTS` in the concat log or on a `-c copy -f null` pass,
3. `silencedetect` over a 6 s window at each seam finds nothing.

Four episodes joined this way were frame-exact and seam-clean. Run the normal QC block afterwards
anyway.

## Batch script

`scripts/render_batch.sh` (env config block at the top) is the shape that survived the run:

- **Idempotent** — skips episodes whose final already exists, so a relaunch resumes. To re-render
  after a lock change, first move the old parts and joined file into `<final>/superseded-<date>/`;
  keep them until the new ones pass QC.
- **One render at a time**, with a 90 s gap and `taskkill /F /IM chrome-headless-shell.exe` before
  each start. Back-to-back starts produced transient `VIDEO_SOURCE_UNRENDERABLE ffmpeg_failed`
  and readiness timeouts even though all proxies probed and decoded cleanly.
- Clears stale `.hf-transaction-*` directories **only when no render process is alive**; one that
  exists during a run belongs to that run.
- Pre-flight before the first render: no render alive, no Studio preview
  (`hyperframes preview --status`), `assets/clips` resolving to the 1 s-keyframe proxies, target
  drive free > 8 GB per episode, and a 6-second smoke render from a one-shot check project using
  the exact production flags — its log must show `streaming-encode gate … enabled:true` and no
  `sparse keyframes` warning.
- Per-episode logs plus a summary log carrying one `START` / `DONE` / `FAILED` line per item.
- Launch detached with `nohup`, then watch the summary log. Before relaunching, check the process
  list: a killed wrapper can leave a sibling `sh` alive, and two copies race for the same output.

`grep 'Failure summary'` in a per-episode log gives the failed stage and error.

## Process hygiene

- **Stop a render by PID, never by image name.** Claude Code itself runs on node, so killing every
  `node.exe` ends the session. List the render's own processes by command line, then kill in this
  order so nothing restarts: the batch shell(s) running `render_batch.sh`, the node process whose
  command line names `hyperframes.mjs render`, the `chrome-headless-shell` tree, any `ffmpeg`
  child. On Windows:
  `Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'render_batch|hyperframes|headless|ffmpeg' } | Select ProcessId, ParentProcessId, Name, CommandLine`
  then `Stop-Process -Id <pid>` / `taskkill /PID <pid> /T /F`. A stalled run left alone
  auto-retries from frame 0 and burns another full part.
- **Let a wrapper shell finish.** Killing one mid-assembly cost a run its ffprobe and produced
  `audioPadTrim: failed to probe`.
- **Keep the machine idle during a render.** Concurrent ffmpeg — QC sweeps, thumbnails, decode
  checks, Studio — has stalled captures.
- If the CLI's install was patched (the npx cache copy was edited to extract source-video frames
  sequentially instead of via `Promise.all`, curing transient `VIDEO_SOURCE_UNRENDERABLE`), invoke
  `bin/hyperframes.mjs` by absolute path with `node`. Any `npx hyperframes@latest` reinstalls a
  clean copy and silently drops the patch.

## Expected noise

`Some video elements did not decode` after the 300 s init timeout fires on every page holding many
`<video>` elements and is harmless — the renderer falls back to extracted frames and the output is
correct. Read past it and keep watching the frame counter.

## Settled dead ends

Two fixes were tried against the stalls and did not move them: deep seeks into long proxies, and
per-shot proxies. Both are fine to keep for page weight; neither buys a whole-episode render of a
long episode. The parts split is the fix.
