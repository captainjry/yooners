# Intake interview — step 1, and again at steps 2 and 3

The interview settles every decision that is the user's before work is spent on it. It follows
the grilling shape: a **decision tree**, asked in **rounds**.

- The **frontier** is every decision whose prerequisites are settled. Ask the whole frontier in
  one round, numbered, each question with your **recommended answer** and the fact it rests on.
  Then wait.
- **Facts are yours, decisions are the user's.** Read the card, the metadata and the transcripts
  for everything they can tell you (dates, raw seconds per day, frame rate, spoken language,
  free disk space), and put the result inside the question: "Day 3 has 321 s of footage".
- A decision that hangs on an answer still open belongs to the next round.
- "Just go" from the user means: take every recommended answer and list each one in `BRIEF.md`
  under Notes as a derived default.

Every answer lands in one place, the same turn it is given: a key in `series.json`, or a line in
`BRIEF.md` naming the question it answered.

## The tree

Each row is a decision, what it needs first, and where the answer lives.

### Round 1 — after the metadata scan

| Decision | Recommend from | Lands in |
|---|---|---|
| Which date prefixes on the card are this trip | contiguous dates; file count per prefix | `BRIEF.md` |
| **Format**: a series of episodes, or one film | total raw runtime and number of shooting days: a short trip or thin days make one film; several full days make a series | `series.json` `format` |
| Name, slug, and the calendar day each prefix maps to | the camera clock, stated as a guess | `series.json` `slug`, `text` |
| Who watches it, and where it is published | — | `BRIEF.md` Intent |
| Delivery geometry and frame rate | the majority of the source files | `series.json` `canvas`, `fps` |
| Where `<media>` lives | free space against the estimated proxy and final sizes | `series.json` paths |

### Round 2 — once format is settled

| Decision | Recommend from | Lands in |
|---|---|---|
| Series: the episode split and a runtime per episode | one episode per meaningful day, travel folded into the first and last; runtime from that day's raw seconds | `series.json` `episodes` |
| Film: the target runtime and what a chapter is (a day, or a place) | raw seconds overall; days when the trip moves daily, places when it stays put | `BRIEF.md`, storyboard plan |
| The look: keep the default design, or a palette and typefaces of their own | default | `series.json` `design` |
| Music: the mood, and whether they pick per episode or once | per episode for a series, one bed for a film | `BRIEF.md` Customizations |
| A teaser reel at the end, or none | yes | `BRIEF.md` |
| Anyone or anything that must stay off screen | — | `BRIEF.md` Notes |

### Round 3 — after the visual index (step 2)

| Decision | Recommend from | Lands in |
|---|---|---|
| The place name for each day or stop, spelled as it should appear on screen | your reading of signs and scenery in the sheets, offered as guesses to correct | `tools/stamps.json`, `subtitles.keep_words` |
| What to do with each `privacy` hit: trim around it, or drop the clip | trim when the moment matters | visual index `privacy` |
| Which moments must be in | the `anchor` clips | `BRIEF.md` Notes |

### Round 4 — after transcription (step 3)

| Decision | Recommend from | Lands in |
|---|---|---|
| Caption language, and a translated track or none | the language the transcripts report | `series.json` `lang` |
| The `subtitles` block: speech script, scripts that never occur, known mis-hearings | the transcripts' languages and their recurring errors | `series.json` `subtitles` |
| Original audio throughout, or music-led stretches | speech seconds per day | `BRIEF.md` Customizations |

## Done when

The frontier is empty: every row above has an answer in its place, or a recommended answer
logged as a derived default, and the user has confirmed the summary of rounds 1 and 2 before
step 2 begins.
