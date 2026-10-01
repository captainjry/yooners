# yooners

Agent skills by [captainjry](https://github.com/captainjry). Each skill is a self-contained folder
under `skills/` with a `SKILL.md` (the instructions an agent follows) and its own README.

## Skills

| Skill | What it does |
|---|---|
| [dji-vlog-series](skills/dji-vlog-series) | Turn a folder of raw camera clips into a multi-episode travel-vlog series or one long film, plus a vertical teaser: intake interview, indexing, storyboard, cut lists, ffmpeg renders, QC, and a YouTube upload sheet. |
| [social-reel](skills/social-reel) | Cut a vertical Reel/Short from existing footage in the style of a reference reel: shot survey, 9:16 crop, static lockup, embedded bed or silent render for a platform sound. |
| [soulslike-run-book](skills/soulslike-run-book) | Build a one-page HTML run book for a soulslike, themed after the game: a map per area with numbered stops from where you stand, missable quests and loot, what locks at each boss, capped upgrade budgets, endings, and the 100% achievement roadmap. |

## Install

### Claude Code

The repo is a plugin marketplace. Add it once, then install the plugins you want:

```
/plugin marketplace add captainjry/yooners
/plugin install vlog@yooners
/plugin install soulslike@yooners
```

| Plugin | Skills | Invoke as |
|---|---|---|
| `vlog` | dji-vlog-series, social-reel | `/vlog:dji-vlog-series`, `/vlog:social-reel` |
| `soulslike` | soulslike-run-book | `/soulslike:soulslike-run-book` |

`/plugin marketplace update yooners` then `/plugin update <plugin>@yooners` pulls a newer version.

### Other agents

Install with the [`skills`](https://skills.sh) CLI, which works for Codex, Cursor, and 70+ other
agents. The quickest route is interactive — it asks which skills and which agents:

```sh
npx skills add captainjry/yooners
```

Or name them with flags. `-a` takes one or more agents; `-g` installs for every project (omit it to
install into the current project only):

```sh
npx skills add captainjry/yooners --skill <skill> -g -a <agent>
```

| Agent | `-a` value | Project skills folder |
|---|---|---|
| Codex | `codex` | `.agents/skills/` |
| Cursor | `cursor` | `.agents/skills/` |
| Gemini CLI | `gemini-cli` | `.agents/skills/` |
| GitHub Copilot | `github-copilot` | `.agents/skills/` |
| OpenCode | `opencode` | `.agents/skills/` |
| Windsurf | `windsurf` | `.windsurf/skills/` |

Several at once: `-a codex cursor`. Every agent: `-a '*'`. Passing an unknown `-a` value
prints the full list of supported agents.

### Manual install

Without Node, clone the repo and copy the skill's folder into your agent's skills folder from the
table above:

```sh
git clone https://github.com/captainjry/yooners
cp -r yooners/skills/<skill> .agents/skills/     # Codex, Cursor, Gemini CLI, Copilot, OpenCode
```

Each skill's README lists its requirements and any agent-specific parts.

## License

MIT — see [LICENSE](LICENSE).
