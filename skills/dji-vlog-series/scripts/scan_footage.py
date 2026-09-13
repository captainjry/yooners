"""Step 1-2: metadata scan, three-frame index, and contact sheets for a folder of raw clips.

Produces the outputs every later tool reads: source-metadata.json, frame-index.json, thumbnails/,
sheets/, sheet-manifest.json. Read-only on the source directory.

  python scan_footage.py --source <source> --out <review>
  python scan_footage.py --source <source> --out <review> --metadata-only
  python scan_footage.py --source <source> --out <review> --prefix DJI_YYYYMM --per-sheet 6

Outputs in --out:
  source-metadata.json   [{file, streams:[{codec_name, codec_type, width, height,
                           color_space, color_transfer, color_primaries, avg_frame_rate}]}]
  frame-index.json       [{file, duration, frames:[{seconds, path}]}]
  thumbnails/<stem>-N.jpg
  sheets/sheet-NN.jpg + sheet-manifest.json  [{sheet, path, files:[...]}]

Write complete-visual-index.json yourself after looking at every sheet (see
reference/footage-index.md for its schema); this script cannot judge what is in a frame.
"""
import argparse, json, subprocess, sys
from pathlib import Path

AP = argparse.ArgumentParser()
AP.add_argument("--source", required=True, help="directory of original clips (read-only)")
AP.add_argument("--out", required=True, help="working directory for indexes and thumbnails")
AP.add_argument("--ext", default=".MP4", help="source extension, case-insensitive")
AP.add_argument("--prefix", default="", help="only files starting with this (e.g. DJI_202602 for one month's shoot)")
AP.add_argument("--samples", type=int, default=3, help="frames extracted per clip")
AP.add_argument("--per-sheet", type=int, default=6, help="clips per contact sheet")
AP.add_argument("--sheet-tile", default="3x6", help="cols x rows for the sheet montage")
AP.add_argument("--ffmpeg", default="ffmpeg")
AP.add_argument("--ffprobe", default="ffprobe")
AP.add_argument("--metadata-only", action="store_true")
AP.add_argument("--sheets-only", action="store_true", help="rebuild contact sheets from an existing frame-index.json")
A = AP.parse_args()

SRC, OUT = Path(A.source), Path(A.out)
OUT.mkdir(parents=True, exist_ok=True)
THUMBS = OUT / "thumbnails"; SHEETS = OUT / "sheets"

files = sorted(p for p in SRC.iterdir()
               if p.suffix.lower() == A.ext.lower() and p.name.startswith(A.prefix))
if not files:
    sys.exit(f"no {A.ext} files under {SRC} matching prefix {A.prefix!r}")
print(f"{len(files)} clips")

# --- 1. metadata -------------------------------------------------------------------------
meta = []
if A.sheets_only:
    index = json.load(open(OUT / "frame-index.json", encoding="utf-8"))
    files = [Path(e["file"]) for e in index]
for i, p in enumerate([] if A.sheets_only else files, 1):
    r = subprocess.run([A.ffprobe, "-v", "error", "-show_streams", "-show_format",
                        "-of", "json", str(p)], capture_output=True, text=True)
    d = json.loads(r.stdout or "{}")
    meta.append({"file": p.name, "programs": [], "streams": [
        {k: s.get(k) for k in ("codec_name", "codec_type", "width", "height", "color_space",
                               "color_transfer", "color_primaries", "avg_frame_rate")}
        for s in d.get("streams", [])],
        "duration": float(d.get("format", {}).get("duration", 0) or 0)})
    if i % 25 == 0: print(f"  probed {i}/{len(files)}")
if not A.sheets_only:
    json.dump(meta, open(OUT / "source-metadata.json", "w", encoding="utf-8"), indent=2)
    print("wrote source-metadata.json")
if A.metadata_only:
    sys.exit(0)

# --- 2. three frames per clip ------------------------------------------------------------
THUMBS.mkdir(exist_ok=True)
fractions = [(k + 1) / (A.samples + 1) for k in range(A.samples)]
if not A.sheets_only: index = []
for i, (p, m) in enumerate([] if A.sheets_only else zip(files, meta), 1):
    dur = m["duration"]
    frames = []
    for k, fr in enumerate(fractions):
        t = round(dur * fr, 3)
        dst = THUMBS / f"{p.stem}-{k}.jpg"
        if not dst.exists():
            subprocess.run([A.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                            "-ss", f"{t:.3f}", "-i", str(p), "-frames:v", "1",
                            "-vf", "scale=640:-1", str(dst)], check=False)
        frames.append({"seconds": t, "path": str(dst)})
    index.append({"file": p.name, "duration": dur, "frames": frames})
    if i % 25 == 0: print(f"  extracted {i}/{len(files)}")
if not A.sheets_only:
    json.dump(index, open(OUT / "frame-index.json", "w", encoding="utf-8"), indent=2)
    print("wrote frame-index.json")

# --- 3. contact sheets -------------------------------------------------------------------
SHEETS.mkdir(exist_ok=True)
manifest = []
for n, start in enumerate(range(0, len(files), A.per_sheet), 1):
    group = index[start:start + A.per_sheet]
    tiles = [f["path"] for e in group for f in e["frames"]]
    dst = SHEETS / f"sheet-{n:02d}.jpg"
    # tile= consumes successive frames of ONE stream, so the separate image inputs must be
    # scaled to a common size and concatenated first (fix 2026-09-10; before this every
    # sheet was one real tile plus black).
    args = [A.ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
    for t in tiles: args += ["-i", t]
    scaled = "".join(f"[{i}:v]scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:-1:-1:black,setsar=1[s{i}];" for i in range(len(tiles)))
    chain = "".join(f"[s{i}]" for i in range(len(tiles)))
    fc = f"{scaled}{chain}concat=n={len(tiles)}:v=1:a=0[v];[v]tile={A.sheet_tile}:padding=4:margin=4:color=black"
    args += ["-filter_complex", fc, "-frames:v", "1", "-q:v", "3", str(dst)]
    subprocess.run(args, check=False)
    manifest.append({"sheet": n, "path": str(dst), "files": [e["file"] for e in group]})
json.dump(manifest, open(OUT / "sheet-manifest.json", "w", encoding="utf-8"), indent=2)
print(f"wrote {len(manifest)} sheets + sheet-manifest.json")
print("NEXT: read every sheet as an image, then write complete-visual-index.json")
