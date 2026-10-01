---
name: soulslike-run-book
description: >
  Build a run book: a one-page HTML game guide for a soulslike (Elden Ring, Sekiro, Dark Souls,
  Bloodborne, Lies of P and kin) that navigates the player area by area from where they stand
  now — a map per area with numbered, tickable stops, missable quests and loot, what locks at
  each boss, capped upgrade budgets with every unit located, one-way forks, endings, and the
  100% achievement roadmap. Use when the user asks for a guide, navigator, map, walkthrough or
  missables list for such a game, wants a 100% / platinum plan, or reports a new position in an
  existing run book ("I just beat the Capra Demon").
---

# Soulslike run book

One page the player keeps open beside the game. It sits between playing blind and following a
video walkthrough: the page shows where to go next and what must be done before the door
closes; the fights and the story stay the player's. The reader is tabbed out of a game for a
few seconds, so the page answers at a glance: a picture first, a few words second.

`templates/run-book.html` is a component kit with `{{PLACEHOLDER}}` text: every component the
page can be built from, plus the Navigator's area picker, map styles and tick script. Its
opening comment lists them. The page's structure and its look are decided per game (step 4).

## The six words the page is built on

- **Navigator** — one map per area with numbered markers, and the same numbers in a short list
  beside it. This is where the player lives; every other tab is reference.
- **Lock** — an event (almost always a boss death or an area transition) after which something
  is gone for the run. Every lock on the page names its trigger and what it closes.
- **Budget** — a resource the run hands out a fixed count of (upgrade materials, skill points,
  key items). Every budget has a total, a where-list with one row per unit, and a committed
  spend order.
- **Fork** — a one-way choice (boss-soul trade, covenant, quest answer, ending decision). Every
  fork shows both sides and the pick.
- **Tick** — a checkbox the player owns, saved in their browser. One thing has one tick id for
  the life of the page; where the thing shows twice (a stop and its where-list row, a stop and
  its quest step) both boxes carry that id and move together. A ticked stop dims on the map.
- **Your run** — a `.note.info` callout opening `<strong>Your run:</strong>`. All
  player-specific text lives in these and in the Now tab; the rest of the page is true for any
  player. This split is what makes a position update a small edit.

## Spoiler line

Write mechanics, locations, item names and quest steps in full. Name bosses as landmarks. Give a
story beat only where a fork needs it to be chosen. Leave boss strategy and lore to the game,
unless the user asks for them.

A name that is itself a reveal (an ending, a hidden achievement, a late boss whose identity is
the twist) goes in a `span.spoil`, blurred until tapped. The sentence around it carries the
whole instruction: "Give the third boss's soul to the smith", with only the name gated.

## New run book

1. **Intake.** Settle: game and platform/version; DLC in or out (ask when the DLC ships inside
   the edition being played); current position (last checkpoint rested at, last boss killed) or
   "not started"; build and weapon goal, or "decide for me"; completion goal (finish, all
   quests, 100% achievements) and how many runs they will accept. Ask only for what the request
   left out; default goal 100%.
   *Done when* each answer fills a header chip or the dek of the page.

2. **Research.** → `reference/research.md`. The categories are independent; hand them to
   parallel workers when the agent has them.
   *Done when* every category in that file is filled or marked "this game has none", every
   number on its way to the page has a source, every count has two agreeing sources or a
   stated disagreement, and every lock has a trigger.

3. **Commit the plan.** Choose for the player, once: one build line, one spend order per budget
   that adds up to the budget's total, one pick per fork, one ending route per run, one area
   order. Where the position is mid-game, plan from it: whatever is already spent or locked is
   stated plainly as lost, with when it comes back (NG+, next run).
   *Done when* no budget is overspent, no two picks need the same fork item, and every shop or
   trainer the plan relies on is usable with the planned stats.

4. **Pilot one area.** Before anything else is built, make a one-area page and show it to the
   user: the player's current area with its map and stops, in this game's own look.
   - **Theme from the game.** Take the palette and typefaces from the game itself: its menus,
     its key art, the materials it keeps returning to. Replace the kit's colour tokens and font
     stacks; a run book for another game should be recognisable as another game.
   - **Structure from the game.** Decide which tabs exist and in what order from this game's
     systems, named as the game names them. The kit's panels are a parts bin.
   - **Map.** → `reference/area-maps.md`.
   *Done when* the user has seen the pilot and approved its look and its map style, or their
   changes are applied.

5. **Write the stops.** For every area in the plan's order: the stops in walking order, each
   one line with a landmark the player can see, the thing to do there, and what it is for, and
   each with a tick whose id is `<area>-<short-name>` (`03-ember`). Optional detours are marked
   with where they rejoin. The last stop is the boss or exit; under the list, a lock note names
   everything that boss or exit closes. A hub area also carries a "Go now" exit and the "Later"
   exits to leave alone.
   *Done when* every missable item, quest step, NPC and budget unit from the research appears
   as a stop in exactly one area, upstream of the lock that closes it.

6. **Draw the maps.** → `reference/area-maps.md`. Draw the player's current area and the areas
   ahead of it up to the next major milestone; later areas ship as stop lists and gain their
   maps on a position update. Map drawing is independent per area; hand areas to parallel
   workers when the agent has them, with the reference material already fetched for them.
   *Done when* every drawn map passes the check in that file and has been looked at once in a
   rendered page.

7. **Write the Now tab.** From the current position: "Do now, before <next lock>", "Catch-up
   check — still fixable", "Right after <next lock>", and "Already locked" stated plainly. For
   a run not started, open with "Before the first save": each pre-game choice, the pick, and
   whether it can change later, locked rows first.
   *Done when* a player who reads only this tab can play to the next lock and lose nothing.

8. **Fill the reference tabs** for this game's systems: build, budgets, forks, quests, endings,
   achievements, the untaught mechanics, and whatever else the game has.
   - Each budget's where-list has one row per unit (where, how, what it needs first), each row
     ticked with its stop's id.
   - Each quest is an ordered list of steps, each step ticked with its stop's id and carrying
     its lock, plus one "Breaks if" line.
   - Untaught mechanics are ranked by the time they save, a claim and its consequence each.
   - Add a `figure` diagram where a rule is structural (a loop, a window, a fork, a budget
     against its cost). Put a "Your run" callout under every section the plan touches.
   *Done when* every where-list has as many rows as its budget's total, and every achievement
   flagged missable points at the stop, quest or fork that earns it.

9. **Check the page.** Run `python scripts/check_run_book.py <file>` until it prints `clean`:
   it covers leftover placeholders, the slug, stop and marker numbering, marker spacing, map
   classes, tick ids and where-list totals. Then render the page once in a browser: every tab
   switches, the area picker steps through all areas, a tick survives a reload, nothing scrolls
   sideways at phone width, light and dark both read. Then read the Now tab and the current
   area against the research once more — a wrong lock costs the player a run.
   *Done when* all three pass. Tell the user what the checks caught and you corrected.

10. **Deliver.** Save as `<game-slug>-run-book.html` where the user keeps such files and give
    the path. Publish it to a hosting or artifact tool only when the user asks for a link. The
    saved file is the source for every later update.

## Position update

The user reports progress ("I'm at chapter IX", "killed Ornstein and Smough"). The saved file is
the plan; the ticks are what the player has done. Read the file, and take the ticks as text
when the user pastes them (footer, "Back up or move your ticks" → Export), then

1. Move the position chip and the "You are here" callout; make that area the one the picker
   opens on.
2. Rewrite the Now tab for the new position (step 7).
3. Re-state every "Your run" callout: locks now behind the player read as done or as lost.
   The exported ticks settle which; without them, ask about each unconfirmed missable upstream
   of the new position that a fork or budget depends on.
4. Draw the maps for the next stretch of areas (step 6).
5. Re-run step 3's check if the user changed build, picked a fork differently, or missed a
   budget item.
6. Keep every existing tick id as it is, so the player's saved ticks still match. Save over
   the same file and run step 9's script; republish only if it was published before.

*Done when* no callout speaks of a dead boss as alive, the Now tab's first list starts from
the new position, the current area and the ones up to the next milestone have maps, and the
script prints `clean`.
