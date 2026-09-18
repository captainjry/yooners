# Measuring a reference reel — step 1

Everything runs inside the user's logged-in Chrome tab via `javascript_tool`; Instagram serves a
login page to a plain fetch. Nothing is downloaded: frames are drawn to an in-page canvas, audio is
decoded in memory and only numbers leave the page. `scripts/reference_reel.js` holds the four
snippets; paste one at a time.

## 1. Canvas and duration

`probe`: pauses the `<video>` and returns `duration, videoWidth, videoHeight`. A 1080×608 reel is a
landscape 16:9 frame posted vertically; 1080×1920 is native. Match the reference's canvas unless
the user says otherwise.

## 2. Contact sheet

`sheet`: seeks the video to 19 timestamps, draws each frame into a 5-column canvas with its time
stamped, and swaps the page body for the image; screenshot it. Zoom on any tile to read type.
Write the shot list from it: what each shot shows, its length, where people sit in frame, the
text treatment (persistent lockup vs per-shot captions vs none), the grade.

Instagram's reel and audio-page tabs both go unresponsive to screenshots when heavy media is
loading; if `Page.captureScreenshot` times out twice, read the numbers instead of the pixels.

## 3. Picture cut points

`cuts`: plays the reel once, samples a 48×86 frame every 40 ms, and returns the times where the
frame difference peaks above 4× the median with 0.5 s spacing. ±0.1 s. A shot the differencer
misses (same location, slow move) shows as one long slot — check against the sheet.

These cut points are a **cut grid** the editor already fitted to this sound. Copy them for
platform mode; for embedded mode they are only a rhythm reference.

## 4. Sound hit map (platform mode)

Open the reel's audio page (the "Audio" link under the caption, `/reels/audio/<id>/`), which
serves a plain `<audio>` element with a CDN URL. `hits`: fetches it, decodes with Web Audio,
computes a 10 ms RMS envelope, an onset-strength curve, autocorrelation tempo candidates, and
onset peaks. Returns:

- `best` tempo and the top candidates. A flat top-8 (scores within 5%) means **no steady beat**;
  cut on hits, and lean on the reference's cut points.
- `hits`: onset times with 0.2 s minimum spacing. The strongest single hit is usually the
  section change; give it the longest shot.
- `sec`: 1 s energy — the structure (sparse intro, sustained body, tail).

Read the page text too: "Original audio · <user>" means a user-uploaded sound (still attachable
in-app); a song title means a licensed track (attachable in-app in most regions).

## 5. Offset check

Lay the reference's cut points beside the hits. When every cut sits 0.1–0.4 s after a hit, the
reference starts the sound at 0:00 and the render is cut from 0. If they line up only after a
constant shift, that shift is the sound's start offset — record it in `AUDIO-MAP.md` and tell the
user to set the same start when attaching.

Capturing the reel's own audio through a `MediaElementSource` returned silence on Instagram (the
element is MSE-backed); the cut-point match is the offset evidence, not a waveform.

## Output — `AUDIO-MAP.md`

Reference URL and id, canvas, duration, audio identity (name, id, original vs licensed), the
tempo verdict, the hit list, the reference's cut points, the offset, and the proposed slot grid
(cut points nudged onto the nearest hit within 0.25 s, frame-snapped). Render length ≤ sound
length.
