# Publish sheet — step 12

Uploading is the user's step. The deliverable here is a sheet they can paste from without
thinking, so every box on the upload page has exactly one block in the file.

Write `<media>/final/YOUTUBE.txt`. Header first, stating what goes where and the settings that are
identical for every episode:

```
<SERIES> <YEAR> — YouTube upload sheet
Each episode below has exactly three blocks. Each block goes into ONE box:
  [TITLE]        -> the Title box (one line; a <language> alternative follows if wanted)
  [DESCRIPTION]  -> the Description box (paste whole; chapters and credit are already inside)
  [TAGS]         -> the Tags box under "Show more" (paste the line; YouTube splits on commas)
Same for all: Playlist "<series>" · Category Travel & Events · Video language <lang>
· Not made for kids · Subtitles: upload <project>/renders/subtitles/eNN.<lang>.srt
· Thumbnail: <media>/final/thumbnails/<Series>-ENN.jpg · Visibility: <choice>
· End screen: add "next video" in the last 5 s (the end card is built for it)
Files: <media>/final/<Series>-ENN.mp4 (<geometry>, <fps> fps)
```

Then one block per episode, separated by a rule, headed with the episode number, title, measured
runtime and bed name:

- **`[TITLE]`** — `<Series> EP.N — <episode title> | <place> → <place>`, plus a translated
  alternative when the audience is not English-first.
- **`[DESCRIPTION]`** — a short paragraph in the diary's own voice, then chapter timestamps (one
  per beat, `M:SS Beat name · Place`), then the series line, then
  `Original audio throughout. <Language> captions available (CC).`, then the music credit with the
  licence URL, then hashtags. Chapter times come from the cut list's cumulative beat seconds and
  must match the rendered file — check the first and last against the video.
- **`[TAGS]`** — places first, then the day, then the series and generic travel tags, in both
  languages. One comma-separated line.

Order the episodes so the first few are contiguous on the channel; YouTube's end-screen "next
video" works best when the neighbours are already up.

Keep names consistent across the sheet, the end cards and the channel. If the series is renamed
after the episodes render, the end cards keep the old name — say so plainly rather than
re-rendering ten 4K episodes for a title.

Append the teaser's own block at the end of the same file (`social-reel`, `reference/audio-modes.md`).
