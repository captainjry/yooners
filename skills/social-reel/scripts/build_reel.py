"""Render one vertical reel from a shot-cut hard-cut grid. ffmpeg + Pillow, no browser.

  python build_reel.py --config reel.json                 # final render
  python build_reel.py --config reel.json --draft          # half-canvas fast proof
  python build_reel.py --config reel.json --dry-run        # write .cmd.txt/.filter.txt and stop
  python build_reel.py --config reel.json --force          # re-render an existing output
  python build_reel.py --config reel.json --cpu            # libx264 instead of NVENC

reel.json fields: proxies|source (clip dir), output, canvas [w,h], fps, cuts (path to cuts.json),
lockup {lines, position, top_px, color, shadow}, audio {mode: bed|silent, bed, gain, fade_out},
design.fonts (sans, mono, optional serif).

cuts.json is the single source of timing: {"shots": [{"file", "in", "out", "x_offset"?}, ...]},
in/out in source seconds, ordered - the render is a straight hard cut through the list. Each shot
is scaled to the canvas height keeping aspect, then cropped to the canvas width; x_offset (source
pixels, default centred) shifts the crop window per shot.

Text layer (dji-vlog-series/scripts/textlayers.py's render_lockup) is one static PNG overlaid for
the whole length - no animation. Audio is either a bed trimmed to length with a fade-out, or no
audio stream at all (the platform sound is attached at upload).

Writes <out>.cmd.txt / .filter.txt / .log next to the output, and prints an ffprobe PASS/FAIL on
frame count ("audio: none" when silent).
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path

AP = argparse.ArgumentParser()
AP.add_argument("--config", required=True, help="reel.json")
AP.add_argument("--draft", action="store_true", help="half canvas, fast preset")
AP.add_argument("--dry-run", action="store_true", help="write the command + filter script only")
AP.add_argument("--force", action="store_true", help="re-render even if the output exists")
AP.add_argument("--cpu", action="store_true", help="libx264 instead of NVENC")
A = AP.parse_args()

# sibling skill, installed beside this one - render_lockup and the Design/font machinery live there
_SIBLING = Path(__file__).resolve().parent.parent.parent / "dji-vlog-series" / "scripts"
if not (_SIBLING / "textlayers.py").exists():
    sys.exit(f"dji-vlog-series/scripts/textlayers.py not found at {_SIBLING} - "
              "install the dji-vlog-series skill beside social-reel")
sys.path.insert(0, str(_SIBLING))
from textlayers import Design, render_lockup                               # noqa: E402

CFG = json.load(open(A.config, encoding="utf-8"))
CFGDIR = Path(A.config).resolve().parent


def cfgpath(v):
    return (CFGDIR / v).resolve()


CLIPS_DIR = cfgpath(CFG.get("proxies") or CFG["source"])
OUTPUT = cfgpath(CFG["output"])
FPS = CFG.get("fps", 25)
CANVAS_W, CANVAS_H = CFG.get("canvas", [1080, 1920])
CUTS = json.load(open(cfgpath(CFG["cuts"]), encoding="utf-8"))
SHOTS = CUTS["shots"]
LOCKUP = CFG["lockup"]
AUDIO = CFG.get("audio", {"mode": "silent"})
DESIGN = Design(CFG, CFGDIR)


def f6(x):
    return f"{x:.6f}"


# --- source geometry, so a source-pixel x_offset can be converted into the scaled frame ------

_DIMS = {}


def src_dims(path):
    if path not in _DIMS:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                              "-show_entries", "stream=width,height", "-of", "json", str(path)],
                             capture_output=True, text=True).stdout
        s = json.loads(out)["streams"][0]
        _DIMS[path] = (s["width"], s["height"])
    return _DIMS[path]


def crop_x(src_path, x_offset, oh, ow):
    """Left edge of the ow x oh crop window, in the frame scaled to height oh (even pixels)."""
    sw, sh = src_dims(src_path)
    scale = oh / sh
    scaled_w = (int(sw * scale) // 2) * 2
    x = (scaled_w - ow) / 2 + x_offset * scale
    return max(0, min(scaled_w - ow, int(round(x))))


# --- plan --------------------------------------------------------------------------------------

def plan():
    shots = []
    frames = 0
    for s in SHOTS:
        src = CLIPS_DIR / s["file"]
        dur = round(s["out"] - s["in"], 6)
        nf = int(round(dur * FPS))
        shots.append({"src": str(src), "ss": s["in"], "dur": dur, "nf": nf,
                     "x_offset": s.get("x_offset", 0)})
        frames += nf
    return {"shots": shots, "total_frames": frames, "total": frames / FPS}


# --- lockup PNG ----------------------------------------------------------------------------

def lockup_png(ow, oh):
    dst = OUTPUT.parent / f"{OUTPUT.stem}.lockup.png"
    dst.parent.mkdir(parents=True, exist_ok=True)
    render_lockup(DESIGN, (ow, oh), LOCKUP["lines"], LOCKUP.get("position", "top"),
                 LOCKUP.get("top_px", 200), LOCKUP.get("color", "#FFFFFF"),
                 LOCKUP.get("shadow")).save(dst)
    return dst


# --- ffmpeg graph --------------------------------------------------------------------------

def still(frames):
    return f"loop=loop={frames - 1}:size=1:start=0,setpts=N/{FPS}/TB,settb=1/{FPS}"


def graph(P, lockup_path, ow, oh):
    ins, fl = [], []
    n = 0
    for i, s in enumerate(P["shots"]):
        ins += ["-ss", f6(s["ss"]), "-i", s["src"]]
        x = crop_x(s["src"], s["x_offset"], oh, ow)
        fl.append(f"[{n}:v]setpts=PTS-STARTPTS,fps={FPS},scale=-2:{oh},crop={ow}:{oh}:{x}:0,"
                  f"format=yuv420p,select='lt(n\\,{s['nf']})',setpts=PTS-STARTPTS[v{i}];")
        n += 1
    segs = "".join(f"[v{i}]" for i in range(len(P["shots"])))
    fl.append(f"{segs}concat=n={len(P['shots'])}:v=1:a=0[bodyv];")
    ins += ["-i", str(lockup_path)]
    fl.append(f"[{n}:v]format=rgba,scale={ow}:{oh},format=yuva420p,{still(P['total_frames'])}[lockup];")
    fl.append(f"[bodyv][lockup]overlay=eof_action=pass[vout];")
    n += 1

    a = None
    if AUDIO.get("mode") == "bed":
        bed = cfgpath(AUDIO["bed"])
        gain = AUDIO.get("gain", 1.0)
        fade = AUDIO.get("fade_out", 1.0)
        ins += ["-i", str(bed)]
        fl.append(f"[{n}:a]atrim=0:{f6(P['total'])},asetpts=PTS-STARTPTS,aresample=48000,"
                  f"aformat=sample_fmts=fltp:channel_layouts=stereo,volume={gain},"
                  f"afade=t=out:st={f6(max(0, P['total'] - fade))}:d={f6(fade)}[aout];")
        a = "aout"
        n += 1
    return ins, "\n".join(fl).rstrip(";"), ("vout", a)


def command(P, lockup_path, fscript):
    ow, oh = (CANVAS_W // 2, CANVAS_H // 2) if A.draft else (CANVAS_W, CANVAS_H)
    ins, ftext, (v, a) = graph(P, lockup_path, ow, oh)
    fscript.write_text(ftext, encoding="utf-8")
    if A.cpu:
        enc = ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p"]
    else:
        enc = ["-c:v", "h264_nvenc", "-preset", "p1" if A.draft else "p6", "-tune", "hq",
              "-rc", "vbr", "-cq", "28" if A.draft else "19", "-b:v", "0",
              "-maxrate", "80M", "-bufsize", "160M", "-profile:v", "high", "-pix_fmt", "yuv420p"]
    maps = ["-map", f"[{v}]"] + (["-map", f"[{a}]", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
                                 if a else ["-an"])
    return (["ffmpeg", "-hide_banner", "-y", "-nostdin"] + ins +
            ["-filter_complex_script", str(fscript)] + maps +
            ["-fps_mode", "cfr", "-r", str(FPS), "-frames:v", str(P["total_frames"]),
             "-t", f6(P["total"])] + enc +
            ["-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(OUTFILE)])


def write_cmd(cmd, stem):
    Path(f"{stem}.cmd.txt").write_text(
        " ".join(f'"{c}"' if " " in c else c for c in cmd) + "\n", encoding="utf-8")


def run(cmd, log, expect_frames):
    t0 = time.time(); last = 0.0
    with open(log, "wb") as err:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err, text=True, bufsize=1)
        cur = {}
        for line in p.stdout:
            k, _, val = line.strip().partition("=")
            cur[k] = val
            if k == "progress" and (time.time() - last > 10 or val == "end"):
                el = time.time() - t0
                fr = int(cur.get("frame", 0) or 0)
                eta = (expect_frames - fr) / max(1e-6, fr / el) if fr else 0
                print(f"  {fr}/{expect_frames} frames  fps={cur.get('fps','?')}  "
                      f"speed={cur.get('speed','?')}  {el:.0f}s elapsed  eta {eta:.0f}s", flush=True)
                last = time.time()
        p.wait()
    if p.returncode != 0:
        print(f"  FAILED (exit {p.returncode}) - see {log}")
        for ln in open(log, encoding="utf-8", errors="replace").read().splitlines()[-12:]:
            print("    " + ln)
        return None
    return time.time() - t0


def probe(f):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
                          "-show_entries", "stream=nb_read_packets:format=duration",
                          "-of", "json", str(f)], capture_output=True, text=True).stdout
    j = json.loads(out)
    return int(j["streams"][0]["nb_read_packets"]), float(j["format"]["duration"])


# --- run -----------------------------------------------------------------------------------

P = plan()
print(f"reel: {len(P['shots'])} shots, {P['total_frames']} frames = {P['total']:.2f}s, "
      f"audio {AUDIO.get('mode', 'silent')}")

OUTFILE = OUTPUT.with_name(f"{OUTPUT.stem}-draft{OUTPUT.suffix}") if A.draft else OUTPUT
STEM = OUTFILE.with_suffix("")

if OUTFILE.exists() and not A.force and not A.dry_run:
    sys.exit(f"exists, skipping (use --force): {OUTFILE}")

OUTFILE.parent.mkdir(parents=True, exist_ok=True)
ow, oh = (CANVAS_W // 2, CANVAS_H // 2) if A.draft else (CANVAS_W, CANVAS_H)
lockup_path = lockup_png(ow, oh)

cmd = command(P, lockup_path, Path(f"{STEM}.filter.txt"))
write_cmd(cmd, STEM)

if A.dry_run:
    print(f"  dry run: {STEM}.cmd.txt, {STEM}.filter.txt")
    sys.exit(0)

secs = run(cmd, Path(f"{STEM}.log"), P["total_frames"])
if secs is None:
    sys.exit(1)

frames, dur = probe(OUTFILE)
ok = frames == P["total_frames"]
print(f"{'PASS' if ok else 'FAIL'}  {OUTFILE.name}  {frames} frames "
      f"(expected {P['total_frames']}), {dur:.2f}s, {OUTFILE.stat().st_size/1e6:.0f}MB, "
      f"{secs:.0f}s wall" + ("" if AUDIO.get("mode") == "bed" else "  audio: none"))
sys.exit(0 if ok else 1)
