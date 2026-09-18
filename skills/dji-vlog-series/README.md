# dji-vlog-series

An agent skill that turns a folder of raw camera clips (DJI, phone, action cam) into a
multi-episode travel-vlog series plus a vertical teaser: footage indexing, storyboard, per-episode
cut lists, 4K proxies, rendering, QC, loudness normalization and a YouTube upload sheet.

Proven on 168 clips (3.1 h) → ten 4K episodes + a 39 s short, and on 89 clips (29 min) → two 4K
episodes + a 20 s reel.

Everything renders with ffmpeg; the title card, place stamps, end card and thumbnails are PNGs
drawn with Pillow. No browser, no compositor, no Node.

The agent follows `SKILL.md` step by step. You stay in charge of two gates: approving the
storyboard, and locking the cut before the final renders. Uploading stays with you.

## Contents

```
SKILL.md       the workflow: 12 steps, each with a completion criterion
reference/     detail for each stage (footage index, storyboard & cuts, build, render, QC, publish)
scripts/       the tools (Python and POSIX sh); run any with --help or read its header
templates/     BRIEF.md, HANDOFF.md, cut-list worker brief, series.json config
```

## Requirements

- **ffmpeg / ffprobe** on `PATH` (an NVIDIA GPU with NVENC is used when present; `--cpu` renders
  with libx264 instead)
- **Python 3.10+** with `Pillow` (text layers and thumbnails), `faster-whisper` (transcription,
  CUDA GPU recommended), `librosa` and `numpy` (teaser tempo measurement)
- A POSIX shell for the `.sh` scripts (Git Bash works on Windows)

## Self-test

Prove the render toolchain on any machine in under a minute, with no footage:

```sh
python scripts/make_fixture.py --out /tmp/fixture --fonts /tmp/fixture/fonts
python scripts/build_episodes.py --config /tmp/fixture/series.json --draft   # must print PASS
```

## Install

```sh
npx skills add captainjry/yooners --skill dji-vlog-series -g -a <agent>
```

`<agent>` is `claude-code`, `codex`, `cursor`, `gemini-cli`, `github-copilot`, `opencode`,
`windsurf`, or any other agent the CLI supports; list several to install for each. Omit `-g` to scope
it to the current project. See the [root README](../../README.md#install) for skills folders and a
manual install without Node.

Then ask your agent to "turn this footage folder into a vlog series". In Claude Code you can also type
`/dji-vlog-series`.

### Agents other than Claude Code

`SKILL.md` uses the open Agent Skills format (YAML frontmatter plus markdown), so any agent that loads
skills runs it; an agent without skills support can read `SKILL.md` as plain instructions. A few parts
assume Claude Code:

| Part | Claude Code | Elsewhere |
|---|---|---|
| Step 5, one subagent per episode | Subagents | Run the worker brief once per episode, sequentially |
| Step 7, sourcing music via `/media-use` | Media skill | Pick cleared beds yourself and record the credit line |
| Step 12, teaser via `/social-reel` | Reel skill | Cut the teaser by hand from the cut lists |

## Platform notes

The workflow was built on Windows. The one Windows-specific command in the docs is
`Get-CimInstance` for finding a live render's PID; use `ps` / `pkill` elsewhere.

## License

MIT — see [LICENSE](../../LICENSE).
