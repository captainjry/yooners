# Area maps

The Navigator is one schematic map per area with numbered markers, and the same numbers in a
short list beside it. The player tabs out of the game, finds the next number, and tabs back.
The picture carries the route; the list carries what each stop is.

A map is a diagram of the level: which spaces connect, in what order the route passes them,
and where each stop sits. Connections and order are exact. Shapes are approximate, and the
page says so once.

## Before drawing

1. **Stops first.** Write the area's stops in walking order (SKILL.md, step 5). The map is
   drawn to those stops, numbered 1..n.
2. **Find a layout reference.** In order of preference: a fan-made area map on the game's
   wiki; the wiki walkthrough's room-by-room text; the stop descriptions alone. Look at a
   reference image, then draw a simpler plan of your own; leave its artwork, labels and legend
   behind. Most games have reference maps for a few areas only, and none for the rest: the
   text sources are the normal case.
3. **Pick the projection.** A plan (top-down) for areas that spread out. A side-on section,
   levels stacked with ladders between them, for areas that are mainly vertical. Say which in
   the `aria-label`.

## The SVG

One `<svg viewBox="0 0 W H" role="img" aria-label="...">` inside `div.map`, W 480–560, H
420–820. The page's stylesheet paints it; the SVG carries classes only, so it follows the
theme in light and dark.

| Class | Element | Means |
|---|---|---|
| `room` | rect / circle / path | an enclosed space; `room up` for an upper floor or raised walkway |
| `open` | path | open ground: cliffs, forest, swamp, a bridge over a drop |
| `door` | small rect | a locked door or key gate |
| `gate` | small rect | a main or boss door |
| `fog` | small rect | a boss fog or one-way threshold |
| `ladder` | small rect | ladder, lift or stairs between levels |
| `lbl` | text | room names, capitals, at most three words; every exit labelled with where it leads |
| `route` | polyline | the walking path through every marker in number order, kept inside rooms and corridors; a second polyline for a second pass |
| `mk k-KIND` | g > circle + text | one marker per stop: `<g class="mk k-KIND" data-n="N"><circle cx cy r="12"/><text x y>N</text></g>`, boss `r="15"` |

Marker kinds: `rest` (checkpoint), `boss` (boss, mini-boss, invasion, hazard), `npc` (person,
merchant, smith, faction), `loot` (anything picked up), `exit` (exit, ladder, lift, shortcut),
`route` (a waypoint or instruction). The stop row's number chip uses the same kind class, so
map and list match by colour as well as by number.

A stop that happens outside the area (a hand-in at the hub, a preparation step) gets its
marker at the map's edge beside the matching exit label.

Aim for 12 to 30 shapes, corridors about 24 px wide, 4 to 9 labels. Entrance at the bottom or
left, boss or exit at the top or right, unless the reference reads better another way.

## Done when

For each map: it parses; markers are numbered exactly 1..n for the area's n stops; every
marker centre sits at least 14 px inside the viewBox and at least 26 px from every other;
every class is from the table; the SVG carries no `fill`, `stroke` or `style` attribute. Then
render the page once and look at each new map: the route line is readable, no label sits under
a marker, and nothing renders black (an unknown class).

`python scripts/check_run_book.py <file>` checks everything in the first sentence except the
parse; the rendered look is yours.

## When a map cannot be drawn

Some areas resist a diagram: a single open field, a maze the sources never describe, a
boss-rush corridor. Give that area `class="area nomap"` and its stop list alone, and say in one
line that it has no map. A list that is right beats a map that is invented.
