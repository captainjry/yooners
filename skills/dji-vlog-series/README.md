# dji-vlog-series

An agent skill that turns a folder of raw camera clips (DJI, phone, action cam) into a
multi-episode travel-vlog series plus a vertical teaser: footage indexing, storyboard, per-episode
cut lists, 4K proxies, rendering, QC, loudness normalization and a YouTube upload sheet.

Proven on 168 clips (3.1 h) → ten 4K episodes + a 39 s short, and on 89 clips (29 min) → two 4K
episodes + a 20 s reel.

The agent follows `SKILL.md` step by step. You stay in charge of two gates: approving the
storyboard, and locking the cut before the final renders. Uploading stays with you.

## Contents

```
SKILL.md       the workflow: 13 steps, each with a completion criterion
reference/     detail for each stage (footage index, storyboard & cuts, build, render, QC, publish)
scripts/       the tools (Python and POSIX sh); run any with --help or read its header
templates/     BRIEF.md, HANDOFF.md, cut-list worker brief, series.json config
```

## Requirements

- **ffmpeg / ffprobe** on `PATH` (an NVIDIA GPU with NVENC is used when present; libx264 is the
  fallback)
- **Python 3.10+** with `faster-whisper` (transcription, CUDA GPU recommended), `Pillow` (thumbnails),
  `librosa` and `numpy` (teaser tempo measurement)
- **HyperFrames CLI** (`npx hyperframes`) and Node.js, for compositions,
  storyboard preview and rendering
- A POSIX shell for the `.sh` scripts (Git Bash works on Windows)

## Install

### Claude Code

Clone the repo and copy this skill's folder into your skills directory:

```sh
git clone https://github.com/captainjry/yooners
cp -r yooners/skills/dji-vlog-series ~/.claude/skills/
```

Use `.claude/skills/` inside a project instead to scope it to that project. Then ask Claude to
"turn this footage folder into a vlog series", or type `/dji-vlog-series`.

### Other agents

`SKILL.md` uses the open Agent Skills format (YAML frontmatter plus markdown), so any agent that
loads skills can use it; otherwise point your agent at `SKILL.md` as instructions. A few parts
assume Claude Code:

| Part | Claude Code | Elsewhere |
|---|---|---|
| `/hyperframes`, `/hyperframes-cli`, `/hyperframes-audio`, `/media-use` | HyperFrames skills | Use the HyperFrames docs directly |
| Step 13, teaser via `/social-reel` | HyperFrames skill | Cut the teaser by hand from the cut lists |
| Step 5, one subagent per episode | Subagents | Run the worker brief once per episode, sequentially |

## Platform notes

The workflow was built on Windows, and a few commands in the docs are Windows-specific:
`taskkill` and `Get-CimInstance` for process control (use `pkill` / `ps` elsewhere), and a
directory junction for `<project>/assets/clips` (use a symlink elsewhere).

## License

MIT — see [LICENSE](../../LICENSE).
