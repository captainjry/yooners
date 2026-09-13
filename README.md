# yooners

Agent skills by [captainjry](https://github.com/captainjry). Each skill is a self-contained folder
under `skills/` with a `SKILL.md` (the instructions an agent follows) and its own README.

## Skills

| Skill | What it does |
|---|---|
| [dji-vlog-series](skills/dji-vlog-series) | Turn a folder of raw camera clips into a multi-episode travel-vlog series plus a vertical teaser: indexing, storyboard, cut lists, 4K renders, QC, and a YouTube upload sheet. |

## Install

Install with the [`skills`](https://skills.sh) CLI, which works for Claude Code, Codex, Cursor, and
70+ other agents. The quickest route is interactive — it asks which skills and which agents:

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
| Claude Code | `claude-code` | `.claude/skills/` |
| Codex | `codex` | `.agents/skills/` |
| Cursor | `cursor` | `.agents/skills/` |
| Gemini CLI | `gemini-cli` | `.agents/skills/` |
| GitHub Copilot | `github-copilot` | `.agents/skills/` |
| OpenCode | `opencode` | `.agents/skills/` |
| Windsurf | `windsurf` | `.windsurf/skills/` |

Several at once: `-a claude-code codex cursor`. Every agent: `-a '*'`. Passing an unknown `-a` value
prints the full list of supported agents.

### Manual install

Without Node, clone the repo and copy the skill's folder into your agent's skills folder from the
table above:

```sh
git clone https://github.com/captainjry/yooners
cp -r yooners/skills/<skill> .agents/skills/     # Codex, Cursor, Gemini CLI, Copilot, OpenCode
cp -r yooners/skills/<skill> ~/.claude/skills/   # Claude Code, all projects
```

Each skill's README lists its requirements and any agent-specific parts.

## License

MIT — see [LICENSE](LICENSE).
