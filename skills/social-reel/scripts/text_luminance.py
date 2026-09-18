#!/usr/bin/env python
"""Brightest pixel inside a text band of a frame. White type must reach 255; a lower peak means
something (a scrim, an opacity, a blend) paints over the text, which the contrast audit misses.

  python text_luminance.py --image frame.png --band 150,330,930,590
  python text_luminance.py --video final.mp4 --at 10.78 --band 150,330,930,590
"""
import argparse, subprocess, tempfile, os
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("--image"); ap.add_argument("--video"); ap.add_argument("--at", type=float, default=0.0)
ap.add_argument("--band", required=True, help="x0,y0,x1,y1 in canvas pixels")
ap.add_argument("--expect", type=int, default=255)
ap.add_argument("--ffmpeg", default="ffmpeg")
a = ap.parse_args()

src = a.image
if a.video:
    src = os.path.join(tempfile.mkdtemp(), "f.png")
    subprocess.run([a.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", "%.3f" % a.at,
                    "-i", a.video, "-frames:v", "1", src], check=True)
x0, y0, x1, y1 = map(int, a.band.split(","))
im = Image.open(src).convert("L").crop((x0, y0, x1, y1))
peak = max(im.getdata())
verdict = "OK" if peak >= a.expect - 3 else "DIMMED"
print("brightest pixel in band: %d / 255 -> %s" % (peak, verdict))
raise SystemExit(0 if verdict == "OK" else 1)
