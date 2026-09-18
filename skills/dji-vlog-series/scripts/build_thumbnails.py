"""Step 7: YouTube thumbnails - hero still plus episode title, rendered with Pillow via textlayers.

  python build_thumbnails.py --config series.json --map thumbnails.json --out <media>/final/thumbnails

thumbnails.json:  {"01": {"title": "Travel in, together", "still": "assets/storyboard/<stem>-0.jpg"}, ...}
  `still` is a path relative to the project (config's `project` dir). Any 16:9 still works; the
  storyboard extractions are already there and already chosen.

Output: <out>/<slug>-ENN.jpg at 1280x720, JPEG quality 90.
"""
import argparse, json, sys
from pathlib import Path

from textlayers import Design, render_thumb

AP = argparse.ArgumentParser()
AP.add_argument("--config", required=True)
AP.add_argument("--map", required=True)
AP.add_argument("--out", required=True)
A = AP.parse_args()

CFG = json.load(open(A.config, encoding="utf-8"))
MAP = json.load(open(A.map, encoding="utf-8"))
NAME = CFG.get("slug", "Series")
EYEBROW = CFG.get("text", {}).get("thumb_eyebrow", "EP.{n} OF {total}")
CONFIG_DIR = Path(A.config).resolve().parent
BASE = CONFIG_DIR / CFG.get("project", ".")
OUT = Path(A.out); OUT.mkdir(parents=True, exist_ok=True)

D = Design(CFG, BASE)

for ep in sorted(MAP):
    title, still = MAP[ep]["title"], MAP[ep]["still"]
    eyebrow = EYEBROW.format(n=int(ep), total=len(MAP))
    still_path = BASE / still
    if not still_path.exists():
        print(f"e{ep}: FAILED - still not found: {still_path}"); continue
    img = render_thumb(D, still_path, eyebrow, title)
    dst = OUT / f"{NAME}-E{ep}.jpg"
    img.save(dst, quality=90)
    print(ep, img.size, dst.stat().st_size // 1024, "KB")
