"""Optional: cut ONE proxy per SHOT for one episode, instead of one whole-clip proxy per file.

Why: the heaviest episode held 45 <video> elements over 8.2 GB of media across 21 files (largest
1.91 GB / 257 s), several seeking 137-199 s into a long proxy. Per-shot proxies make that ~45 files,
~516 s total, largest ~24 s, every data-media-start ~1 s. This relieves page weight; on its own it
did NOT cure the capture stalls (reference/render.md) - the beat-range parts split does.

  python make_shot_proxies.py --episode 04 --cut-lists <review>/clip-review \
      --frame-index <review>/frame-index.json --source <source> \
      --out <media>/clips-4k-g25/e04-shots            # DRY RUN: writes a command list only
  python make_shot_proxies.py ... --run               # encode (45 4K NVENC jobs; idle machine only)

Numbering: <stem>__s<NN>.mp4 where NN is the 1-based shot index in the same beat/shot iteration
order build_episodes.py uses, so the generator derives the filename with no manifest lookup.
Encode flags are byte-for-byte the whole-clip proxy set.
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path

AP = argparse.ArgumentParser()
AP.add_argument("--episode", required=True)
AP.add_argument("--cut-lists", required=True)
AP.add_argument("--frame-index", required=True)
AP.add_argument("--source", required=True)
AP.add_argument("--out", required=True)
AP.add_argument("--width", type=int, default=3840)
AP.add_argument("--height", type=int, default=2160)
AP.add_argument("--fps", type=int, default=25)
AP.add_argument("--handle", type=float, default=1.0)
AP.add_argument("--no-autorotate", default="")
AP.add_argument("--clip-number-field", type=int, default=2)
AP.add_argument("--ffmpeg", default="ffmpeg")
AP.add_argument("--cmdfile", default="", help="where to write the command list (default: <out>/_commands.sh)")
AP.add_argument("--run", action="store_true", help="encode now instead of only writing the list")
A = AP.parse_args()

W, H = A.width, A.height
MAXRATE, BUF = ("60M", "120M") if W >= 3000 else ("16M", "32M")
SRC, OUT = Path(A.source), Path(A.out)
OUT.mkdir(parents=True, exist_ok=True)
NOROT = {s.strip() for s in A.no_autorotate.split(",") if s.strip()}
CMDFILE = Path(A.cmdfile) if A.cmdfile else OUT / "_commands.sh"

fi = {e["file"]: e for e in json.load(open(A.frame_index, encoding="utf-8"))}
cut = json.load(open(Path(A.cut_lists) / f"e{A.episode}.json", encoding="utf-8"))

jobs, manifest, n = [], {}, 0
for beat in cut["beats"]:
    for s in beat["shots"]:
        n += 1
        f = s["file"]; stem = Path(f).stem
        dur = fi[f]["duration"]
        start = max(0.0, s["in"] - A.handle); end = min(dur, s["out"] + A.handle)
        dst = OUT / f"{stem}__s{n:02d}.mp4"
        parts = f.split("_")
        clipno = parts[A.clip_number_field] if len(parts) > A.clip_number_field else ""
        args = [A.ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
        if clipno in NOROT: args += ["-noautorotate", "-display_rotation", "0"]
        args += ["-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(SRC / f),
                 "-map", "0:v:0", "-map", "0:a:0",
                 "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
                        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1",
                 "-r", str(A.fps), "-c:v", "h264_nvenc", "-preset", "p5",
                 "-g", str(A.fps), "-keyint_min", str(A.fps), "-bf", "0",
                 "-rc", "vbr", "-cq", "21", "-b:v", "0", "-maxrate", MAXRATE, "-bufsize", BUF,
                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                 "-movflags", "+faststart", str(dst)]
        jobs.append((n, f, start, end, dst, args))
        manifest[f"s{n:02d}"] = {"file": f, "shot_index": n, "offset": round(start, 3),
                                 "end": round(end, 3), "proxy": dst.name}

json.dump(manifest, open(OUT / "_shots.json", "w", encoding="utf-8"), indent=1)
with open(CMDFILE, "w", encoding="utf-8") as fh:
    for _, _, _, _, _, args in jobs:
        fh.write(" ".join(f'"{a}"' if " " in a else a for a in args) + "\n")
print(f"{len(jobs)} shot proxies planned -> {OUT}")
print(f"command list: {CMDFILE}   manifest: {OUT/'_shots.json'}")
if not A.run:
    print("DRY RUN. Re-run with --run, or execute the command list on an idle machine.")
    sys.exit(0)

t0 = time.time()
for i, (n, f, start, end, dst, args) in enumerate(jobs, 1):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        print("FAILED", dst.name, r.stderr[-300:], flush=True); continue
    print(f"[{i}/{len(jobs)}] {dst.name} {start:.1f}-{end:.1f}s "
          f"{os.path.getsize(dst)/1e6:.0f}MB elapsed={time.time()-t0:.0f}s", flush=True)
print("DONE")
