"""Self-test fixture for the render pipeline: synthetic clips plus the config files around them.

  python make_fixture.py --out <dir> --fonts <dir with the two TTFs>
  python build_episodes.py --config <dir>/series.json --draft      # must print PASS

Writes <dir>/proxies/*.mp4 (testsrc2 + a sine tone per clip, encoded like a real proxy: 25 fps,
keyframe every second) with _ranges.json, a two-beat cut list in <dir>/clip-review/e01.json whose
in/out points are deliberately off the frame grid, stamps.json, frame-index.json, a looping bed,
and series.json for a 1080p canvas. Nothing here touches a real project: it exists so the episode
renderer can be proved on any machine, and so a change to the graph can be checked in a minute.
"""
import argparse, json, subprocess, sys
from pathlib import Path

AP = argparse.ArgumentParser()
AP.add_argument("--out", required=True, help="fixture directory (created)")
AP.add_argument("--fonts", default="", help="directory holding the sans/mono TTFs")
AP.add_argument("--fps", type=int, default=25)
AP.add_argument("--size", default="1080p", choices=["1080p", "4k"], help="clip and canvas size")
AP.add_argument("--beats", type=int, default=2, help="beats in the cut list (3 shots each)")
A = AP.parse_args()

OUT = Path(A.out).resolve()
PROX = OUT / "proxies"
PROX.mkdir(parents=True, exist_ok=True)
(OUT / "clip-review").mkdir(exist_ok=True)

W, H = (3840, 2160) if A.size == "4k" else (1920, 1080)
# stem, seconds, hue shift (so each clip reads differently), tone Hz, filename hour
CLIPS = [
    ("FIX_20260906093000_0001_D", 11.0, 0, 220, 9),
    ("FIX_20260906094500_0002_D", 9.0, 60, 294, 9),
    ("FIX_20260906101500_0003_D", 12.0, 120, 349, 10),
    ("FIX_20260906183000_0004_D", 10.0, 180, 392, 18),
    ("FIX_20260906184500_0005_D", 8.0, 240, 440, 18),
    ("FIX_20260906190000_0006_D", 11.0, 300, 523, 19),
]


def run(args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr[-2000:])


for stem, secs, hue, hz, _ in CLIPS:
    dst = PROX / f"{stem}.mp4"
    if dst.exists():
        continue
    run(["ffmpeg", "-hide_banner", "-y",
         "-f", "lavfi", "-t", str(secs), "-i", f"testsrc2=size={W}x{H}:rate={A.fps}",
         "-f", "lavfi", "-t", str(secs), "-i", f"sine=frequency={hz}:sample_rate=48000",
         "-vf", f"hue=h={hue},drawbox=0:0:{W}:120:color=black@0.6:t=fill",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-g", str(A.fps),
         "-keyint_min", str(A.fps), "-bf", "0", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-ac", "2", "-shortest", str(dst)])
    print("clip", dst.name)

bed = OUT / "bgm" / "fixture-bed.m4a"
bed.parent.mkdir(exist_ok=True)
if not bed.exists():
    run(["ffmpeg", "-hide_banner", "-y", "-f", "lavfi", "-t", "60",
         "-i", "sine=frequency=110:sample_rate=48000", "-ac", "2", "-c:a", "aac", "-b:a", "128k", str(bed)])
    print("bed", bed.name)

json.dump({stem: {"file": stem + ".MP4", "offset": 0.0, "end": secs,
                  "proxy": f"proxies/{stem}.mp4", "size": f"{W}x{H}"}
           for stem, secs, _, _, _ in CLIPS},
          open(PROX / "_ranges.json", "w"), indent=1)
json.dump([{"file": stem + ".MP4", "seconds": secs, "fps": A.fps, "size": f"{W}x{H}"}
           for stem, secs, _, _, _ in CLIPS],
          open(OUT / "frame-index.json", "w"), indent=1)

# in/out points off the frame grid on purpose, and one of each audio mode per beat
beats = [
    {"card": "fix-1-morning", "beat_seconds": 0,
     "shots": [(0, 0.9, 7.9, "keep"), (1, 0.3, 5.7, "music-only"), (2, 1.1, 9.35, "duck")]},
    {"card": "fix-2-evening", "beat_seconds": 0,
     "shots": [(3, 0.4, 6.4, "duck"), (4, 0.25, 4.65, "keep"), (5, 2.0, 9.5, "music-only")]},
]
cut = {"episode": "01", "target_runtime_s": 40, "beats": [], "flags": ["synthetic fixture"]}
total = 0.0
beats = [dict(b, card="%s-%d" % (b["card"], i + 1)) for i in range(max(1, A.beats // 2))
         for b in beats][:max(1, A.beats)]
for b in beats:
    shots = []
    for idx, i, o, mode in b["shots"]:
        shots.append({"file": CLIPS[idx][0] + ".MP4", "in": i, "out": o, "audio": mode,
                      "why": "fixture shot", "quote": "", "lang": ""})
        total += o - i
    cut["beats"].append({"card": b["card"], "beat_seconds": round(sum(s["out"] - s["in"] for s in shots), 2),
                         "shots": shots})
cut["episode_seconds"] = round(total, 2)
json.dump(cut, open(OUT / "clip-review" / "e01.json", "w"), indent=1)

stamps = {"_note": "fixture stamps; null = time of day only"}
for i, b in enumerate(cut["beats"]):
    stamps[b["card"]] = None if i % 2 else "Fixture Village %d" % (i + 1)
json.dump(stamps, open(OUT / "stamps.json", "w"), indent=1)

fonts = Path(A.fonts).resolve() if A.fonts else OUT / "fonts"
sans = next(iter(sorted(fonts.glob("*ontserrat*.ttf")) + sorted(fonts.glob("*.ttf"))), None)
mono = next(iter(sorted(fonts.glob("*Mono*.ttf")) + sorted(fonts.glob("*.ttf"))), None)
if not sans or not mono:
    sys.exit(f"no TTFs in {fonts} - pass --fonts <dir with a sans and a mono TTF>")

json.dump({
    "_readme": "Generated by make_fixture.py. python build_episodes.py --config series.json --draft",
    "project": str(OUT).replace("\\", "/"),
    "cut_lists": "clip-review", "stamps": "stamps.json", "frame_index": "frame-index.json",
    "proxies": "proxies", "output": "out", "layers": "layers",
    "slug": "fixture", "lang": "en", "fps": A.fps, "canvas": [W, H], "handle": 1.0,
    "episodes": {"01": {"title": "A fixture episode, rendered end to end", "batch": "6 SEP"}},
    "bed": {"01": "fixture-bed"}, "bed_dir": "bgm", "bed_ext": ".m4a",
    "bed_title_level": 0.45, "bed_ramp": 0.6,
    "bed_level": {"keep": 0.1, "duck": 0.2, "music-only": 0.45},
    "shot_volume": {"keep": 1.0, "duck": 0.6, "music-only": 0.3},
    "shot_edge_fade": 0.12, "title_hold": 4.2, "stamp_hold": 3.2, "end_hold": 3.0,
    "design": {"text_scale": 0.5 if A.size == "1080p" else 1.0, "paper": "#F5F1E8", "ink": "#25302D", "accent": "#6A4432",
               "rule": "#C9A88F",
               "fonts": {"sans": str(sans).replace("\\", "/"), "mono": str(mono).replace("\\", "/")}},
    "text": {"series_line": "FIXTURE · SEPTEMBER 2026",
             "first_series_line": "A FIXTURE SERIES · SEPTEMBER 2026",
             "end_sub": "{batch} · FIXTURE 2026", "end_last": "The end of the fixture.",
             "end_last_sub": "FIXTURE · THE END", "credit": "MUSIC · A SINE WAVE"},
}, open(OUT / "series.json", "w"), indent=1)

print(f"fixture in {OUT}: {len(CLIPS)} clips, cut list {cut['episode_seconds']}s over "
      f"{len(cut['beats'])} beats\nnext: python build_episodes.py --config {OUT / 'series.json'} --draft")
