#!/usr/bin/env python
"""Contact sheets driven by reel.json + cuts.json (see scripts/build_reel.py).

  --mode plan    one frame per shot at its SOURCE in-point, with the 9:16 crop window drawn
  --mode render  one frame per shot at the shot's midpoint of a rendered file (--video)

reel.json supplies canvas, fps, the clip dir (proxies|source) and the cuts.json path; cuts.json
is the shot list: {"shots": [{"file", "in", "out", "x_offset"?}, ...]}. The crop box in plan mode
uses the same scale-to-height-then-crop math as build_reel.py, so what you see here is the
render's actual crop, not an approximation.
"""
import argparse, json, os, re, subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("--config", required=True, help="reel.json")
ap.add_argument("--mode", choices=["plan", "render"], required=True)
ap.add_argument("--video", help="rendered file for --mode render")
ap.add_argument("--out", required=True)
ap.add_argument("--ffmpeg", default="ffmpeg")
ap.add_argument("--title", default="")
a = ap.parse_args()

cfgdir = Path(a.config).resolve().parent
cfg = json.load(open(a.config, encoding="utf-8"))
cuts = json.load(open((cfgdir / cfg["cuts"]).resolve(), encoding="utf-8"))
shots = cuts["shots"]
clips_dir = (cfgdir / (cfg.get("proxies") or cfg["source"])).resolve()
cw, ch = cfg.get("canvas", [1080, 1920])
fps = cfg.get("fps", 25)

# absolute start/end per shot, on the frame grid build_reel.py renders
t = 0.0
for s in shots:
    dur = round(s["out"] - s["in"], 6)
    nf = int(round(dur * fps))
    s["_start"], s["_end"] = t, t + nf / fps
    t += nf / fps

tmp = tempfile.mkdtemp()
_dims = {}


def src_dims(path):
    if path not in _dims:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                              "-show_entries", "stream=width,height", "-of", "json", str(path)],
                             capture_output=True, text=True).stdout
        j = json.loads(out)["streams"][0]
        _dims[path] = (j["width"], j["height"])
    return _dims[path]


def crop_frac(src_path, x_offset):
    """(left, width) of the kept crop window, as a fraction of the SOURCE frame's width."""
    sw, sh = src_dims(src_path)
    scale = ch / sh
    scaled_w = (int(sw * scale) // 2) * 2
    x = max(0, min(scaled_w - cw, (scaled_w - cw) / 2 + (x_offset or 0) * scale))
    return x / scale / sw, cw / scale / sw


def short(name):
    return os.path.splitext(os.path.basename(name))[0][-16:]


def grab(src, t, w, dst):
    subprocess.run([a.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", "%.3f" % t,
                    "-i", src, "-frames:v", "1", "-vf", "scale=%d:-1" % w, dst], check=True)


if a.mode == "plan":
    TW, TH, LB, COLS = 480, int(480 * ch / cw), 50, 4
else:
    TW, TH, LB, COLS = 270, int(270 * ch / cw), 34, 8
ROWS = -(-len(shots) // COLS)
HEAD = 44
sheet = Image.new("RGB", (COLS * TW, HEAD + ROWS * (TH + LB)), (16, 16, 18))
d = ImageDraw.Draw(sheet)
try:
    f = ImageFont.truetype("arial.ttf", 17); fb = ImageFont.truetype("arialbd.ttf", 21)
except Exception:
    f = fb = ImageFont.load_default()
d.text((14, 12), a.title or ("%s sheet — %s" % (a.mode, os.path.basename(a.config))), fill=(235, 235, 235), font=f)

for i, s in enumerate(shots):
    p = os.path.join(tmp, "s%02d.png" % i)
    if a.mode == "plan":
        src = str(clips_dir / s["file"])
        grab(src, s["in"], TW, p)
    else:
        src = a.video
        grab(src, (s["_start"] + s["_end"]) / 2, TW, p)
    im = Image.open(p).convert("RGB").resize((TW, TH))
    x0, y0 = (i % COLS) * TW, HEAD + (i // COLS) * (TH + LB)
    sheet.paste(im, (x0, y0))
    dd = ImageDraw.Draw(sheet)
    if a.mode == "plan":
        fl, fw = crop_frac(src, s.get("x_offset"))
        cx0, cx1 = x0 + fl * TW, x0 + (fl + fw) * TW
        dd.rectangle([cx0, y0 + 1, cx1, y0 + TH - 2], outline=(255, 40, 40), width=3)
        dd.line([(cx0 + cx1) / 2, y0, (cx0 + cx1) / 2, y0 + TH], fill=(255, 40, 40), width=1)
    dd.rectangle([x0, y0 + TH, x0 + TW, y0 + TH + LB], fill=(28, 28, 32))
    off = s.get("x_offset")
    dd.text((x0 + 8, y0 + TH + 3), "%02d  %.2f-%.2fs (%.2fs)  x=%s" %
             (i + 1, s["_start"], s["_end"], s["_end"] - s["_start"], off if off is not None else "centre"),
             fill=(255, 225, 120), font=fb)
    dd.text((x0 + 8, y0 + TH + 26 if a.mode == "plan" else y0 + TH + 19), "%s in %.2f" % (short(s["file"]), s["in"]),
             fill=(180, 180, 190), font=f)
    dd.rectangle([x0, y0, x0 + TW - 1, y0 + TH + LB - 1], outline=(60, 60, 66), width=1)

sheet.save(a.out)
print("wrote", a.out, sheet.size)
