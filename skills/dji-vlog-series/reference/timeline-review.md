# Timeline review — optional, between steps 6 and 8

The user drags cuts on a [FilmCraft](https://github.com/storytold/filmcraft) timeline and the
result lands back in the cut list. The skill runs complete without it: by default a cut change
arrives as a timecode in chat and goes straight into `clip-review/eNN.json`.

## When this branch runs

Both hold:

- the user asked to move cuts by hand, on a timeline, or in FilmCraft;
- FilmCraft is already on the machine: `FILMCRAFT_CLI` is set, or `filmcraft-cli` is on `PATH`.

FilmCraft is the user's own install. When the user asks and it is missing, give them the link
above in one line and take the cut change as a timecode.

## Steps

1. **Push.** `python scripts/review_timeline.py --config <project>/series.json push NN --open`
   *Done when* it prints the shot count and the `.fcproj` path, and that count equals the cut
   list's.

2. **Hand over — gate.** Tell the user the three limits, then wait for "saved":
   - a cut moves outward at most the proxy handle (`handle` in `series.json`, 1 s by default);
   - trim, slip, delete, and reorder inside a beat come back; a razor split, a clip from the bin,
     a speed change, or a shot moved into another beat is a cut-list edit, made in chat;
   - the timeline shows cuts and clip sound; text layers and the bed appear in the draft.

3. **Pull, dry.** `python scripts/review_timeline.py --config <project>/series.json pull NN`
   Show the user every `~` line.
   *Done when* the user confirms the list. On `REFUSED`, make the named edit in the cut list,
   `push NN --force`, and return to step 2.

4. **Write and rebuild.** The same command with `--write`, then `check_cut_list.py`,
   `make_proxies.py`, and that episode's draft.
   *Done when* the validator prints `clean`, every proxy covers its range again, and the new
   draft exists.

Record the review as a dated line in `BRIEF.md`.
