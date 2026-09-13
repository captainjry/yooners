"""Step 8: YouTube thumbnails - hero still plus episode title, rendered THROUGH a HyperFrames
snapshot so the type matches the video exactly (an image library would need the fonts separately
and would not match the video's letter-spacing and shadows).

  python build_thumbnails.py --config series.json --map thumbnails.json \
      --scratch <project>/../<project>-check --out <media>/final/thumbnails

thumbnails.json:  {"01": {"title": "Travel in, together", "still": "assets/storyboard/<stem>-0.jpg"}, ...}
  `still` is a path relative to the scratch project. Any 16:9 still works; the storyboard
  extractions are already there and already chosen.

--scratch is a throwaway one-composition HyperFrames project (its index.html is overwritten each
run). Output: <out>/<Series>-ENN.jpg at 1280x720, under 2 MB.
"""
import argparse, html, json, shutil, subprocess, sys
from pathlib import Path

AP = argparse.ArgumentParser()
AP.add_argument("--config", required=True)
AP.add_argument("--map", required=True)
AP.add_argument("--scratch", required=True, help="throwaway HyperFrames project to snapshot in")
AP.add_argument("--out", required=True)
AP.add_argument("--hyperframes", default="npx hyperframes",
                help='CLI invocation; use "node <abs>/bin/hyperframes.mjs" for a patched install')
AP.add_argument("--width", type=int, default=1280)
AP.add_argument("--height", type=int, default=720)
A = AP.parse_args()

CFG = json.load(open(A.config, encoding="utf-8"))
MAP = json.load(open(A.map, encoding="utf-8"))
D = CFG.get("design", {})
PAPER = D.get("paper", "#F5F1E8"); SANS = D.get("sans", '"Montserrat",sans-serif')
MONO = D.get("mono", '"IBM Plex Mono",monospace')
NAME = CFG.get("slug", "Series")
EYEBROW = CFG.get("text", {}).get("thumb_eyebrow", "EP.{n} OF {total}")
CHECK = Path(A.scratch); OUT = Path(A.out); OUT.mkdir(parents=True, exist_ok=True)
GSAP = CFG.get("gsap", "assets/gsap.min.js")
W, H = A.width, A.height
try:
    from PIL import Image
except ImportError:
    sys.exit("pip install pillow")

for ep in sorted(MAP):
    title, still = MAP[ep]["title"], MAP[ep]["still"]
    eyebrow = EYEBROW.format(n=int(ep), total=len(MAP))
    (CHECK / "index.html").write_text(f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<script src="{GSAP}"></script><style>
html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:#000}}
#root{{position:absolute;inset:0;width:{W}px;height:{H}px;overflow:hidden;background:#000;font-family:{SANS};color:{PAPER}}}
img{{position:absolute;inset:0;width:{W}px;height:{H}px;object-fit:cover}}
#scrim{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,0) 45%,rgba(0,0,0,.72) 100%)}}
#t{{position:absolute;left:56px;right:56px;bottom:52px}}
.eb{{font:400 24px {MONO};letter-spacing:5px;margin-bottom:10px;opacity:.9}}
h1{{margin:0;font-size:78px;font-weight:700;line-height:1.02;letter-spacing:-2.5px;text-shadow:0 3px 24px rgba(0,0,0,.5)}}
</style></head><body>
<div id="root" data-composition-id="thumb" data-start="0" data-duration="1" data-width="{W}" data-height="{H}">
<img class="clip" data-start="0" data-duration="1" src="{still}"><div id="scrim"></div>
<div id="t"><div class="eb">{html.escape(eyebrow)}</div><h1>{html.escape(title)}</h1></div></div>
<script>window.__timelines=window.__timelines||{{}};window.__timelines["thumb"]=gsap.timeline({{paused:true}});</script>
</body></html>''', encoding="utf-8")
    snaps = CHECK / "snaps-thumb"; shutil.rmtree(snaps, ignore_errors=True)
    subprocess.run(A.hyperframes.split() + ["snapshot", ".", "--at", "0.5", "--no-end",
                                            "--output", str(snaps)],
                   cwd=CHECK, shell=False, capture_output=True)
    pngs = sorted(snaps.glob("frame-*.png"))
    if not pngs:
        print(f"e{ep}: FAILED - no snapshot frame produced"); continue
    dst = OUT / f"{NAME}-E{ep}.jpg"
    Image.open(pngs[0]).convert("RGB").save(dst, quality=90)
    print(ep, Image.open(dst).size, dst.stat().st_size // 1024, "KB")
