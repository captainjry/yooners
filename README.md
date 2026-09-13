# yooners

Agent skills by [captainjry](https://github.com/captainjry). Each skill is a self-contained folder
under `skills/` with a `SKILL.md` (the instructions an agent follows) and its own README.

## Skills

| Skill | What it does |
|---|---|
| [dji-vlog-series](skills/dji-vlog-series) | Turn a folder of raw camera clips into a multi-episode travel-vlog series plus a vertical teaser: indexing, storyboard, cut lists, 4K renders, QC, and a YouTube upload sheet. |

## Install

Copy a skill's folder into your agent's skills directory. For Claude Code:

```sh
git clone https://github.com/captainjry/yooners
cp -r yooners/skills/<skill> ~/.claude/skills/
```

Other agents that support the Agent Skills format load the same folder; see each skill's README for
its requirements and any agent-specific parts.

## License

MIT — see [LICENSE](LICENSE).
