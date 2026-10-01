---
name: soulslike-run-book
description: >
  Build a run book: a one-page HTML game guide for a soulslike (Elden Ring, Sekiro, Dark Souls,
  Bloodborne, Lies of P and kin) that navigates the player area by area from where they stand
  now — walking order, missable quests and loot, what locks at each boss, capped upgrade
  budgets, one-way forks, endings, and the 100% achievement roadmap. Use when the user asks for
  a guide, navigator, walkthrough or missables list for such a game, wants a 100% / platinum
  plan, or reports a new position in an existing run book ("I just beat the Capra Demon").
---

# Soulslike run book

One page the player keeps open beside the game. It sits between playing blind and following a
video walkthrough: the page says where to go next and what must be done before the door closes;
the fights and the story stay the player's.

`templates/run-book.html` is the page skeleton: eight tabs, one instance of every component,
`{{PLACEHOLDER}}` text. Its opening comment lists the components. Build every run book from it.

## The five words the page is built on

- **Navigator** — per area, the stops in walking order from the checkpoint the player arrives at
  to the boss. This is the tab the player lives in; every other tab is reference it links to.
- **Lock** — an event (almost always a boss death or an area transition) after which something
  is gone for the run. Every lock on the page names its trigger and what it closes.
- **Budget** — a resource the run hands out a fixed count of (upgrade materials, skill points,
  key items). Every budget has a total, a location list, and a committed spend order.
- **Fork** — a one-way choice (boss-soul trade, covenant, quest answer, ending decision). Every
  fork shows both sides and the pick.
- **Your run** — a `.note.info` callout opening `<strong>Your run:</strong>`. All
  player-specific text lives in these and in the Now tab; the rest of the page is true for any
  player. This split is what makes a position update a small edit.

## Spoiler line

Write mechanics, locations, item names and quest steps in full. Name bosses as landmarks. Give a
story beat only where a fork needs it to be chosen. Leave boss strategy and lore to the game,
unless the user asks for them.

## New run book

1. **Intake.** Settle: game and platform/version; DLC in or out; current position (last
   checkpoint rested at, last boss killed) or "not started"; build and weapon goal, or "decide
   for me"; completion goal (finish, all quests, 100% achievements) and how many runs they will
   accept. Ask only for what the request left out; default DLC out and goal 100%.
   *Done when* each answer fills a header chip or the dek of the page.

2. **Research.** → `reference/research.md`. The categories are independent; hand them to
   parallel workers when the agent has them.
   *Done when* every category in that file is filled or marked "this game has none", every
   count has two agreeing sources or a stated disagreement, and every lock has a trigger.

3. **Commit the plan.** Choose for the player, once: one build line, one spend order per budget
   that adds up to the budget's total, one pick per fork, one ending route per run. Where the
   position is mid-game, plan from it: whatever is already spent or locked is stated plainly as
   lost, with when it comes back (NG+, next run).
   *Done when* no budget is overspent and no two picks need the same fork item.

4. **Write the Navigator.** One card per area in the order the player reaches them. Each stop
   is one line: a landmark the player can see, the thing to do there, and what it is for.
   Stops follow the walking path; optional detours are marked with where they rejoin. The last
   stop of a card is its boss or exit, tagged `lock`, followed by the list of what that lock
   closes. The card for the current position carries the "You are here" callout.
   *Done when* every missable item, quest step and NPC from the research appears as a stop in
   exactly one area card, upstream of the lock that closes it.

5. **Write the Now tab.** From the current position: "Do now, before <next lock>", "Catch-up
   check — still fixable", "Right after <next lock>", and "Already locked" stated plainly.
   *Done when* a player who reads only this tab can play to the next lock and lose nothing.

6. **Fill the reference tabs** — Build, Budgets, Forks, Quests, Endings, 100%. Add, rename or
   drop tabs to fit the game's systems (a tab per major system, as the game names it); draw a
   new icon symbol in the sprite's style when a system needs one. Add a `figure` diagram where
   a rule is structural (a loop, a window, a fork, a budget against its cost). Put a "Your run"
   callout under every section the plan touches.
   *Done when* no `{{` remains in the file and every achievement flagged missable in the 100%
   tab points at the stop, quest or fork that earns it.

7. **Check the page.** Open it in a browser when the agent has one: every tab switches, tables
   scroll inside their wrapper at phone width, light and dark both read. Then read the Now tab
   and the current area card against the research once more — a wrong lock costs the player a
   run.
   *Done when* both pass.

8. **Publish.** Save as `<game-slug>-run-book.html` where the user keeps such files. When the
   agent has a page-publishing tool (a Claude artifact), publish it and tell the user the URL;
   otherwise give the file path to open. The saved file is the source for every later update.

## Position update

The user reports progress ("I'm at chapter IX", "killed Ornstein and Smough"). The page is the
state: read the saved file, then

1. Move the position chip and the "You are here" callout.
2. Rewrite the Now tab for the new position (step 5).
3. Re-state every "Your run" callout: locks now behind the player read as done or as lost —
   ask which when a missable upstream of the new position is unconfirmed and a fork or budget
   depends on it.
4. Re-run step 3's check if the user changed build, picked a fork differently, or missed a
   budget item.
5. Save over the same file and republish to the same URL.

*Done when* no callout speaks of a dead boss as alive, and the Now tab's first list starts from
the new position.
