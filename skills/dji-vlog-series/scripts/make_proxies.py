"""Step 6: cut render-ready proxies of only the source ranges the cut lists use (1 s handles).

Read-only on the originals.

  python make_proxies.py --cut-lists <review>/clip-review --frame-index <review>/frame-index.json \
      --source <source> --out <media>/clips-4k-g25 --size 4k \
      --no-autorotate 0035,0064,0134,0141,0143,0146,0156

Output: <out>/<clip-stem>.mp4 plus <out>/_ranges.json mapping each clip to its proxy offset, so a
composition's data-media-start = source_time - offset. One proxy per source file spanning
min(in)-handle .. max(out)+handle across EVERY use in the series, so a clip shared by two episodes
stays one file. Re-runs skip proxies that already cover their range.

Encode notes that matter (see reference/build.md):
  -g/-keyint_min = fps  -> a keyframe every second. NVENC's 10 s default makes the HyperFrames
                           compiler warn "sparse keyframes ... seek failures and frame freezing".
  --no-autorotate      -> clip numbers whose rotation tag is wrong for landscape content.
  scale+pad+setsar     -> the proxy is already the render geometry.
Point <project>/assets/clips at --out with a directory junction / symlink afterwards.
"""
import argparse, json, os, subprocess, time
from pathlib import Path

AP = argparse.ArgumentParser()
AP.add_argument("--cut-lists", required=True, help="dir of eNN.json cut lists")
AP.add_argument("--frame-index", required=True)
AP.add_argument("--source", required=True)
AP.add_argument("--out", required=True)
AP.add_argument("--size", default="4k", choices=["4k", "1080p", "custom"])
AP.add_argument("--width", type=int, default=0)
AP.add_argument("--height", type=int, default=0)
AP.add_argument("--fps", type=int, default=25)
AP.add_argument("--handle", type=float, default=1.0, help="seconds of padding each side")
AP.add_argument("--no-autorotate", default="", help="comma-separated clip numbers with a wrong rotation tag")
AP.add_argument("--ffmpeg", default="ffmpeg")
AP.add_argument("--clip-number-field", type=int, default=2,
                help="index of the clip number when the filename is split on '_' (DJI_<date>_<NNNN>_D)")
A = AP.parse_args()

W, H = ({"4k": (3840, 2160), "1080p": (1920, 1080)}.get(A.size) or (A.width, A.height))
MAXRATE, BUF = ("60M", "120M") if W >= 3000 else ("16M", "32M")
SRC, OUT = Path(A.source), Path(A.out)
OUT.mkdir(parents=True, exist_ok=True)
NOROT = {s.strip() for s in A.no_autorotate.split(",") if s.strip()}

fi = {e["file"]: e for e in json.load(open(A.frame_index, encoding="utf-8"))}
used = {}
for p in sorted(Path(A.cut_lists).glob("e*.json")):
    if p.stem.endswith("-clips"): continue
    for b in json.load(open(p, encoding="utf-8"))["beats"]:
        for s in b["shots"]:
            lo, hi = used.get(s["file"], (1e9, 0))
            used[s["file"]] = (min(lo, s["in"]), max(hi, s["out"]))

ranges = {}
if (OUT / "_ranges.json").exists():
    ranges = json.load(open(OUT / "_ranges.json", encoding="utf-8"))
t0 = time.time()
for i, (f, (lo, hi)) in enumerate(sorted(used.items()), 1):
    dur = fi[f]["duration"]
    start = max(0.0, lo - A.handle); end = min(dur, hi + A.handle)
    stem = Path(f).stem; dst = OUT / f"{stem}.mp4"
    if dst.exists() and stem in ranges and abs(ranges[stem]["offset"] - start) < 0.01 \
       and ranges[stem]["end"] >= end - 0.01:
        continue
    parts = f.split("_")
    clipno = parts[A.clip_number_field] if len(parts) > A.clip_number_field else ""
    args = [A.ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
    if clipno in NOROT: args += ["-noautorotate", "-display_rotation", "0"]
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
          f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1")
    common = ["-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(SRC / f),
              "-map", "0:v:0", "-map", "0:a:0", "-vf", vf, "-r", str(A.fps)]
    tail = ["-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", str(dst)]
    gpu = ["-c:v", "h264_nvenc", "-preset", "p5", "-g", str(A.fps), "-keyint_min", str(A.fps),
           "-bf", "0", "-rc", "vbr", "-cq", "21", "-b:v", "0", "-maxrate", MAXRATE, "-bufsize", BUF]
    cpu = ["-c:v", "libx264", "-preset", "fast", "-crf", "20", "-g", str(A.fps),
           "-keyint_min", str(A.fps), "-bf", "0"]
    r = subprocess.run(args + common + gpu + tail, capture_output=True, text=True)
    if r.returncode != 0:                     # a few clips reject the GPU path; fall back
        r = subprocess.run(args + common + cpu + tail, capture_output=True, text=True)
        if r.returncode != 0:
            print("FAILED", f, r.stderr[-400:], flush=True); continue
    ranges[stem] = {"file": f, "offset": round(start, 3), "end": round(end, 3),
                    "proxy": f"assets/clips/{stem}.mp4", "size": f"{W}x{H}"}
    json.dump(ranges, open(OUT / "_ranges.json", "w", encoding="utf-8"), indent=1)
    print(f"[{i}/{len(used)}] {f} {start:.1f}-{end:.1f}s {os.path.getsize(dst)/1e6:.0f}MB "
          f"elapsed={time.time()-t0:.0f}s", flush=True)
print("DONE", len(ranges))
print("VERIFY: ffprobe -v error -select_streams v:0 -show_entries frame=key_frame "
      '-of csv=p=0 -read_intervals "%+#60" <a proxy>  ->  expect >= 2 keyframes')
