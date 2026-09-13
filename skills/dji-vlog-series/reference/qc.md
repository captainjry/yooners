# QC — step 11

Run QC only while nothing is rendering. Concurrent ffmpeg has stalled captures.

QC an episode as soon as it is joined and hand it over clean; the user uploads one at a time, so
a clean episode delivered now beats ten delivered together. Parts of one episode render back to
back under the batch script; QC follows the join, not each part.

## Per-file block

`sh scripts/qc_episode.sh <final>.mp4 --expect-duration 405.8 --expect-size 3840x2160`

| Check | Command | Expected |
|---|---|---|
| geometry / duration | `ffprobe -show_entries format=duration:stream=codec_name,width,height` | h264, target size, aac, duration matching the cut list |
| black frames | `blackdetect=d=0.4:pic_th=0.98` | 0 |
| frozen picture | `freezedetect=n=0.001:d=2` | one hit only, at the end card |
| silence | `silencedetect=n=-50dB:d=3` | none, or the end card only |
| loudness | `ebur128=peak=true` | I ≈ −20 LUFS, true peak < −1 dBFS |
| text luminance | `python <social-reel>/scripts/text_luminance.py --video <final> --at <t> --band x0,y0,x1,y1` on one stamped frame | brightest pixel 255 for white type |

A freeze anywhere but the end card, or a black run, means a stalled capture wrote a repeated
frame — re-render rather than patching.

## Look at the contact sheet

```
ffmpeg -i <final>.mp4 -vf "fps=1/20,scale=320:-1,tile=7x3" -frames:v 1 <qc>/E06-sheet.png
```

One pass, one image, then **read it**. This is the only check that catches the failures the
filters miss: a wrong clip in the cut, a sideways shot, a stamp rendered upside down or clipped,
a shot that is black to the eye but not to `blackdetect`. Trailing empty tiles are grid padding
when `duration / 20 < 21`, not missing footage.

## Loudness normalization

Loudness came out inconsistent across the series — −17.7 to −25 LUFS — because the pipeline has no
normalization stage: each episode's level is whatever its per-shot volume automation produced.
Normalize as a separate pass:

`sh scripts/normalize_loudness.sh <final>.mp4 --target -20 --tp -1.5 --lra 14`

Two-pass linear `loudnorm` with the measured values from pass 1, `-c:v copy` so the picture is
untouched and the pass takes minutes rather than an hour. The script moves the original to
`qc/<name>.pre-loudnorm.mp4` and keeps it.

**Normalize before upload.** Re-normalizing an episode already on YouTube means re-uploading it,
which loses the video's URL, views and comments.

## What to record

Write one `qc/eNN-qc.txt` per episode holding the raw output of each check plus a one-line verdict,
and keep the contact sheet beside it. That file is what a later session reads instead of re-running
an hour of sweeps, and it is the evidence behind the status you report.

Report rendered and uploaded as separate columns. An episode being rendered and QC-clean says
nothing about whether it is live.
