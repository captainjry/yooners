# yooners

Agent skills by [captainjry](https://github.com/captainjry). Each skill is a self-contained folder
under `skills/` with a `SKILL.md` (the instructions an agent follows) and its own README.

## Skills

| Skill | What it does |
|---|---|
| [dji-vlog-series](skills/dji-vlog-series) | Turn a folder of raw camera clips into a multi-episode travel-vlog series plus a vertical teaser: indexing, storyboard, cut lists, 4K renders, QC, and a YouTube upload sheet. |

## Install

Install a skill with the [`skills`](https://skills.sh) CLI:

```sh
npx skills add captainjry/yooners --skill <skill> -g -a claude-code
```

`-g` installs for every project (omit it to install into the current project); `-a` picks the agent,
and repeats for several. Run `npx skills add captainjry/yooners` with no flags to choose skills and
agents interactively, or `npx skills --help` for the full agent list.

Without Node, copy the skill's folder into your agent's skills directory by hand:

```sh
git clone https://github.com/captainjry/yooners
cp -r yooners/skills/<skill> ~/.claude/skills/
```

Each skill's README lists its requirements and any agent-specific parts.

## License

MIT — see [LICENSE](LICENSE).
