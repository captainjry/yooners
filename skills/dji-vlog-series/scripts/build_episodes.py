"""Step 9: render one finished episode per cut list with a single ffmpeg graph.

  python build_episodes.py --config series.json                 # every episode, final 4K
  python build_episodes.py --config series.json 01 --draft      # cheap 1080p proof
  python build_episodes.py --config series.json 01 --beats 2-3  # one beat range
  python build_episodes.py --config series.json --layers-only   # only the text PNGs
  --dry-run writes eNN.cmd.txt / eNN.filter.txt and stops; --force re-renders; --cpu = libx264.
Over --split shots (10) the picture is rendered in beat-range parts and joined with -c copy, with
one pass for the sound: a single 4K graph grows by ~0.5 GB a shot because ffmpeg reads ahead.

Timing is on the frame grid: every shot is nf = round(dur*fps) frames and every beat, stamp and
card start is frames_so_far/fps, so sum(shot frames) + end-card frames == the container's frame
count (checked with ffprobe after the run). Shots are cut from the proxies in <proxies> using the
per-stem `offset` in _ranges.json (proxy time = source time - offset).

Text (title card, place stamps, end card) is drawn by textlayers.py into <project>/layers/eNN
(config `layers` overrides). Each overlay input spans the whole episode with its fades at absolute
times and is parked off-canvas outside its window, because ffmpeg's overlay ends the output at the
shorter input and loses frames when gated with enable=.

The looped music bed is shaped by one piecewise-linear `volume` expression (eval=frame) over the
points the automation lane used - title level over the opening, each shot's bed level with
BED_RAMP ramps, 0 by the end of the end card - and mixed with the shot audio in one amix.
"""
import argparse, ctypes, json, os, re, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from textlayers import Design, render_title, render_stamp, render_end

AP = argparse.ArgumentParser()
AP.add_argument("--config", required=True, help="series.json (see templates/series.json)")
AP.add_argument("episodes", nargs="*", help='e.g. 04; empty = every episode in the config')
AP.add_argument("--draft", action="store_true", help="half-size, fast preset, into draft_output")
AP.add_argument("--beats", default="", help="inclusive beat range, e.g. 2-4")
AP.add_argument("--layers-only", action="store_true", help="write the text PNGs and stop")
AP.add_argument("--dry-run", action="store_true", help="write the command + filter script only")
AP.add_argument("--force", action="store_true", help="re-render even if the output exists")
AP.add_argument("--cpu", action="store_true", help="libx264 instead of NVENC")
AP.add_argument("--split", type=int, default=10, metavar="SHOTS",
                help="max shots in one ffmpeg run; longer episodes render in beat-range parts "
                     "and are joined (0 = always one pass)")
A = AP.parse_args()

CFG = json.load(open(A.config, encoding="utf-8"))
CFGDIR = Path(A.config).resolve().parent


def path(key, default=None):
    v = CFG.get(key, default)
    return None if v is None else (CFGDIR / v).resolve()


PROJ = path("project", ".")
CUTS = path("cut_lists")
STAMPS = json.load(open(path("stamps"), encoding="utf-8"))
PROXIES = path("proxies")
OUTDIR = path("output")
DRAFTDIR = path("draft_output") if CFG.get("draft_output") else OUTDIR / "draft"
LAYERS = path("layers") if CFG.get("layers") else PROJ / "layers"

FPS = CFG.get("fps", 25)
CANVAS_W, CANVAS_H = CFG.get("canvas", [1920, 1080])
SLUG = CFG.get("slug", "series")
FORMAT = CFG.get("format", "series")   # "series" = numbered episodes, "film" = one long film
if FORMAT not in ("series", "film"): sys.exit(f'format must be "series" or "film", got {FORMAT!r}')
FILM = FORMAT == "film"
VOL = CFG.get("shot_volume", {"keep": 1.0, "duck": 0.6, "music-only": 0.3})
BED_LEVEL = CFG.get("bed_level", {"keep": 0.10, "duck": 0.20, "music-only": 0.45})
BED = CFG.get("bed", {})
BED_DIR = CFG.get("bed_dir", "assets/bgm")
BED_EXT = CFG.get("bed_ext", ".m4a")
BED_TITLE = CFG.get("bed_title_level", 0.45)
BED_RAMP = CFG.get("bed_ramp", 0.6)
FADE = CFG.get("shot_edge_fade", 0.12)
TITLE_HOLD = CFG.get("title_hold", 4.2)
LABEL_HOLD = CFG.get("stamp_hold", 3.2)
END_HOLD = CFG.get("end_hold", 3.0)
EP = CFG["episodes"]
if FILM and len(EP) != 1: sys.exit('format "film" takes exactly one entry in `episodes`')
TEXT = CFG.get("text", {})
SERIES_LINE = TEXT.get("series_line", "SERIES · DATE")
FIRST_SERIES_LINE = TEXT.get("first_series_line", SERIES_LINE)
END_LAST = TEXT.get("end_last", "The end.")
END_LAST_SUB = TEXT.get("end_last_sub", SERIES_LINE + " · THE END")
END_SUB_FMT = TEXT.get("end_sub", "{batch} · " + SERIES_LINE)
TITLE_SUB_FMT = TEXT.get("title_sub", "{batch} · {stamp}" if FILM else "EPISODE {ep:02d} · {batch} · {stamp}")
CREDIT = TEXT.get("credit", "")
HANDLE = CFG.get("handle", 1.0)
END_FRAMES = int(round(END_HOLD * FPS))

DESIGN = Design(CFG, PROJ)


def r(x):
    return round(x, 3)


def f6(x):
    return f"{x:.6f}"


def time_of_day(fname):
    """Hour from a camera filename like PREFIX_YYYYMMDDhhmmss_NNNN_D.MP4."""
    m = re.search(r"\d{8}(\d{2})\d{4}", fname)
    h = int(m.group(1)) if m else 12
    return ("morning" if h < 11 else "midday" if h < 14 else
            "afternoon" if h < 17 else "evening" if h < 20 else "night")


def bed_file(ep):
    """<bed_dir>/<stem><bed_ext>, resolved against the config dir then the project dir."""
    stem = BED.get(ep)
    if not stem:
        return None
    for base in (CFGDIR, PROJ):
        p = (base / BED_DIR / (stem + BED_EXT)).resolve()
        if p.exists():
            return p
    print(f"  ! bed {stem}{BED_EXT} not found under {BED_DIR}; rendering without a bed")
    return None


# proxy offsets: _ranges.json from make_proxies.py, else the same min(in) - handle rule
def proxy_offsets():
    off = {}
    rng = PROXIES / "_ranges.json" if PROXIES else None
    if rng and rng.exists():
        for stem, v in json.load(open(rng, encoding="utf-8")).items():
            off[stem] = float(v.get("offset", 0.0))
    lowest = {}                     # fallback: make_proxies' own rule, over the whole series
    for p in sorted(CUTS.glob("e*.json")):
        if p.stem.endswith("-clips"):
            continue
        for b in json.load(open(p, encoding="utf-8"))["beats"]:
            for s in b["shots"]:
                stem = Path(s["file"]).stem
                lowest[stem] = min(lowest.get(stem, 1e9), s["in"])
    for stem, lo in lowest.items():
        off.setdefault(stem, max(0.0, lo - HANDLE))
    return off


PROXY_OFFSET = proxy_offsets()


def env_value(pts, x):
    """Linear value of the music-bed envelope at absolute time x."""
    if x <= pts[0]["t"]: return pts[0]["v"]
    if x >= pts[-1]["t"]: return pts[-1]["v"]
    for i in range(1, len(pts)):
        if pts[i]["t"] >= x:
            t0, v0 = pts[i - 1]["t"], pts[i - 1]["v"]; t1, v1 = pts[i]["t"], pts[i]["v"]
            return v1 if t1 == t0 else v0 + (v1 - v0) * (x - t0) / (t1 - t0)
    return pts[-1]["v"]


def slice_env(pts, a, b):
    """The whole-episode envelope restricted to [a, b], rebased to 0, with interpolated edges."""
    out = [{"t": 0.0, "v": r(env_value(pts, a))}]
    out += [{"t": r(p["t"] - a), "v": p["v"]} for p in pts if a < p["t"] < b]
    out.append({"t": r(b - a), "v": r(env_value(pts, b))})
    ded = []
    for p in out:
        if ded and abs(p["t"] - ded[-1]["t"]) < 1e-9: ded[-1] = p
        else: ded.append(p)
    return ded


def env_expr(pts):
    """Piecewise-linear envelope as one flat volume expression, evaluated per frame."""
    terms = []
    for i in range(len(pts) - 1):
        t0, v0 = pts[i]["t"], pts[i]["v"]; t1, v1 = pts[i + 1]["t"], pts[i + 1]["v"]
        if t1 - t0 < 1e-6:
            continue
        if abs(v1 - v0) < 1e-9:
            body = f"{v0:.4f}"
        else:                        # never emit "+-": ffmpeg's expression parser returns NaN
            body = (f"({v0:.4f}{'+' if v1 >= v0 else '-'}{abs(v1 - v0):.4f}"
                    f"*(t-{t0:.3f})/{t1 - t0:.3f})")
        terms.append(f"gte(t,{t0:.3f})*lt(t,{t1:.3f})*{body}")
    terms.append(f"gte(t,{pts[-1]['t']:.3f})*{pts[-1]['v']:.4f}")
    return "+".join(terms)


# --- plan ---------------------------------------------------------------------------------

def plan(ep, lo=None, hi=None):
    """Everything the graph needs: shots on the frame grid, beat rows, layer texts, bed points."""
    d = json.load(open(CUTS / f"e{ep}.json", encoding="utf-8"))
    beats = d["beats"]; nbeats = len(beats)
    lo = lo or 1; hi = hi or nbeats
    if not (1 <= lo <= hi <= nbeats):
        sys.exit(f"e{ep}: --beats {lo}-{hi} outside 1-{nbeats}")
    frames = 0                      # absolute frames since the start of the episode
    off_frames = None               # frames before the selected range
    sel_end = 0
    shots, rows, env = [], [], []
    first_shot_len = None
    first_stamp = ""
    for bi, beat in enumerate(beats, 1):
        beat_frames = frames
        inrange = lo <= bi <= hi
        if inrange and off_frames is None:
            off_frames = beat_frames
        for s in beat["shots"]:
            stem = Path(s["file"]).stem
            dur = round(s["out"] - s["in"], 6)
            nf = int(round(dur * FPS))
            mode = s.get("audio", "keep")
            env.append((frames / FPS, BED_LEVEL.get(mode, 0.10)))
            if inrange:
                if first_shot_len is None:
                    first_shot_len = dur
                shots.append({
                    "src": str(PROXIES / f"{stem}.mp4"),
                    "ss": max(0.0, round(s["in"] - PROXY_OFFSET.get(stem, 0.0), 6)),
                    "dur": dur, "nf": nf, "start": (frames - off_frames) / FPS,
                    "gain": VOL.get(mode, 1.0), "fade": min(FADE, dur / 3), "mode": mode,
                })
            frames += nf
        if inrange:
            sel_end = frames
        place = STAMPS.get(beat["card"])
        tod = time_of_day(beat["shots"][0]["file"])
        text = f"{place} · {tod}" if place else tod.capitalize()
        if bi == 1:
            first_stamp = text
        if inrange:
            rows.append({"beat": bi, "card": beat["card"], "stamp": text,
                         "start": (beat_frames - off_frames) / FPS, "show": bi > 1})
    body_end = frames / FPS                                   # whole episode, for the envelope
    show_title, show_end = lo == 1, hi == nbeats
    body_frames = sel_end - off_frames
    total_frames = body_frames + (END_FRAMES if show_end else 0)

    # bed envelope: title level, per-shot levels with short ramps, fading over the end card
    pts = [{"t": 0, "v": BED_TITLE}]
    last = BED_TITLE
    for (st, lv) in env:
        if abs(lv - last) < 1e-6: continue
        if st > 0: pts.append({"t": r(max(0, st - BED_RAMP / 2)), "v": last})
        pts.append({"t": r(st + BED_RAMP / 2), "v": lv}); last = lv
    pts.append({"t": r(body_end), "v": last})
    pts.append({"t": r(body_end + END_HOLD - 0.2), "v": 0.0})
    pts = [p for i, p in enumerate(pts) if i == 0 or p["t"] >= pts[i - 1]["t"]]

    bed_from = off_frames / FPS
    total = total_frames / FPS
    partial = not (show_title and show_end)
    meta = EP[ep]
    order = sorted(EP)
    series_line = FIRST_SERIES_LINE if ep == order[0] else SERIES_LINE
    is_last = ep == order[-1]
    return {
        "ep": ep, "lo": lo, "hi": hi, "nbeats": nbeats, "shots": shots, "rows": rows,
        "show_title": show_title, "show_end": show_end,
        "hold": r(min(TITLE_HOLD, max(2.5, (first_shot_len or TITLE_HOLD) - 0.3))),
        "body_frames": body_frames, "total_frames": total_frames, "total": total,
        "bed": bed_file(ep), "bed_from": bed_from,
        "bed_pts": slice_env(pts, bed_from, bed_from + total) if partial else pts,
        "title": {"eyebrow": series_line, "title": meta["title"],
                  "sub": TITLE_SUB_FMT.format(ep=int(ep), batch=meta.get("batch", ""), stamp=first_stamp.upper())},
        "end": {"big": END_LAST if is_last else f"Episode {int(ep):02d}",
                "small": END_LAST_SUB if is_last else END_SUB_FMT.format(batch=meta.get("batch", ""), ep=int(ep)),
                "credit": CREDIT},
    }


# --- text layers --------------------------------------------------------------------------

DEPS = max(os.path.getmtime(p) for p in
           (A.config, path("stamps"), Path(__file__).resolve().parent / "textlayers.py"))


def fresh(dst, *extra):
    if A.force or not dst.exists():
        return False
    return os.path.getmtime(dst) >= max([DEPS] + [os.path.getmtime(e) for e in extra])


def layers(P):
    """Write title.png / stamp-<beat>.png / end.png for the whole episode; return the directory."""
    ep = P["ep"]
    d = LAYERS / f"e{ep}"; d.mkdir(parents=True, exist_ok=True)
    canvas = (CANVAS_W, CANVAS_H)
    cut = CUTS / f"e{ep}.json"
    if not fresh(d / "title.png", cut):
        render_title(DESIGN, canvas, P["title"]["eyebrow"], P["title"]["title"], P["title"]["sub"]).save(d / "title.png")
    if not fresh(d / "end.png", cut):
        render_end(DESIGN, canvas, P["end"]["big"], P["end"]["small"], P["end"]["credit"]).save(d / "end.png")
    for row in plan(ep)["rows"]:
        if not row["show"]:
            continue
        dst = d / f"stamp-{row['beat']}.png"
        if not fresh(dst, cut):
            render_stamp(DESIGN, canvas, row["stamp"]).save(dst)
    return d


# --- ffmpeg graph -------------------------------------------------------------------------

def graph(P, ldir, ow, oh, mode="both"):
    """Build (input args, filter script text, [vlabel, alabel]) for one render.

    mode: "both" (picture and sound), "video" (a part of a split render), "audio" (the whole
    episode's sound in one pass, so a split render has no seam in the music).

    No branch of this graph may end before its input does: ffmpeg cuts the whole output at the
    first filter that reports EOF, so a trim/atrim after the cut silently truncates the episode
    (a 5 min episode came out 6 s long). Every cut is therefore made by dropping, not by ending -
    `select` on the video, a `volume` gate on the audio - and the input runs to its own EOF.
    For the same reason the shot audio is placed with adelay+amix instead of concat, which would
    need every segment to end exactly.
    """
    ins, fl = [], []
    geo = (f"scale={ow}:{oh}:force_original_aspect_ratio=decrease,pad={ow}:{oh}:-1:-1,setsar=1")
    n = 0
    mix = []
    for i, s in enumerate(P["shots"]):
        # Picture and sound come from two inputs of the same proxy: with one input feeding both
        # branches ffmpeg decodes a shot's video as soon as amix asks for its audio, and 55
        # buffered 4K shots is tens of GB. No -t on a shot input either - an input that ends
        # because of -t ends the whole output, so the concat plays its first segment and stops.
        # The proxies are cut to the shots they serve, so reading each one to EOF is cheap.
        spec = ["-ss", f6(s["ss"]), "-i", s["src"]]
        end, fd = s["nf"] / FPS, s["fade"]
        if mode != "audio":
            ins += spec
            fl.append(f"[{n}:v]setpts=PTS-STARTPTS,fps={FPS},{geo},format=yuv420p,"
                      f"select='lt(n\\,{s['nf']})',setpts=PTS-STARTPTS[v{i}];")
            n += 1
        if mode != "video":
            ins += spec
            delay = f",adelay={f6(s['start'] * 1000)}:all=1" if s["start"] > 0 else ""
            fl.append(f"[{n}:a]asetpts=PTS-STARTPTS,aresample=48000,"
                      f"aformat=sample_fmts=fltp:channel_layouts=stereo,apad=whole_dur={f6(end)},"
                      f"volume='{s['gain']}*lt(t\\,{f6(end)})':eval=frame,"
                      f"afade=t=in:st=0:d={f6(fd)},afade=t=out:st={f6(end - fd)}:d={f6(fd)}"
                      f"{delay}[a{i}];")
            mix.append(f"[a{i}]")
            n += 1
    segs = "".join(f"[v{i}]" for i in range(len(P["shots"])))
    nseg = len(P["shots"])
    # A still is read once and repeated by the loop filter: -loop 1 -t N ends the input with -t,
    # which loses the frames still in flight, and decoding a 4K PNG per frame is far too slow.
    def still(frames):
        return f"loop=loop={frames - 1}:size=1:start=0,setpts=N/{FPS}/TB,settb=1/{FPS}"
    if mode == "audio":
        fl.append(f"anullsrc=r=48000:cl=stereo:d={f6(P['total'] + 0.5)},"
                  f"aformat=sample_fmts=fltp:channel_layouts=stereo[spine];")
        mix.append("[spine]")
        if P["bed"]:
            ins += ["-stream_loop", "-1", "-ss", f6(P["bed_from"]), "-i", str(P["bed"])]
            fl.append(f"[{n}:a]asetpts=PTS-STARTPTS,aresample=48000,"
                      f"aformat=sample_fmts=fltp:channel_layouts=stereo,"
                      f"volume='{env_expr(P['bed_pts'])}':eval=frame[bed];")
            mix.append("[bed]")
        fl.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=longest:normalize=0[aout]")
        return ins, "\n".join(fl).rstrip(";"), [None, "aout"]
    if P["show_end"]:
        ins += ["-i", str(ldir / "end.png")]
        fl.append(f"[{n}:v]format=rgb24,{geo},{still(END_FRAMES)},"
                  f"format=yuv420p,fade=t=in:d=0.8[ve];")
        segs += "[ve]"; nseg += 1; n += 1
    fl.append(f"{segs}concat=n={nseg}:v=1:a=0[bodyv];")
    if mode == "both":                  # a silent spine keeps the track as long as the picture
        fl.append(f"anullsrc=r=48000:cl=stereo:d={f6(P['total'] + 0.5)},"
                  f"aformat=sample_fmts=fltp:channel_layouts=stereo[spine];")
        mix.append("[spine]")

    # Text layers. Each layer input runs the WHOLE timeline (plus a margin) and carries its fades
    # at absolute times: overlay ends the output at the shorter input, so a layer that stops early
    # truncates the episode. One PNG decode per second (-framerate 1 + fps) keeps that cheap, and
    # the blend is parked off-canvas (x = width) outside its window - overlay's enable= drops
    # frames in this ffmpeg build, moving x does not.
    v = "bodyv"
    span = P["total_frames"] + FPS
    for kind, src, st, hold, fin, fout in (
            [("title", ldir / "title.png", 0.0, P["hold"], 0.7, 0.6)] if P["show_title"] else []) + [
            (f"s{row['beat']}", ldir / f"stamp-{row['beat']}.png", row["start"], LABEL_HOLD, 0.5, 0.5)
            for row in P["rows"] if row["show"]]:
        ins += ["-i", str(src)]
        fl.append(f"[{n}:v]format=rgba,scale={ow}:{oh},format=yuva420p,{still(span)},"
                  f"fade=t=in:st={f6(st)}:d={fin}:alpha=1,"
                  f"fade=t=out:st={f6(st + hold - fout)}:d={fout}:alpha=1[l{kind}];")
        fl.append(f"[{v}][l{kind}]overlay=eof_action=pass:eval=frame:"
                  f"x='if(between(t,{f6(st)},{f6(st + hold)}),0,{ow})'[v{kind}];")
        v = f"v{kind}"; n += 1

    if mode == "both" and P["bed"]:
        ins += ["-stream_loop", "-1", "-ss", f6(P["bed_from"]), "-i", str(P["bed"])]
        fl.append(f"[{n}:a]asetpts=PTS-STARTPTS,aresample=48000,"
                  f"aformat=sample_fmts=fltp:channel_layouts=stereo,"
                  f"volume='{env_expr(P['bed_pts'])}':eval=frame[bed];")
        mix.append("[bed]"); n += 1
    if mode == "both":
        fl.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=longest:normalize=0[aout]")
    return ins, "\n".join(fl).rstrip(";"), [v, "aout" if mode == "both" else None]


def command(P, ldir, outfile, fscript, mode="both"):
    ow, oh = (CANVAS_W // 2, CANVAS_H // 2) if A.draft else (CANVAS_W, CANVAS_H)
    ins, ftext, (v, a) = graph(P, ldir, ow, oh, mode)
    fscript.write_text(ftext, encoding="utf-8")
    aud = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    if mode == "audio":
        return (["ffmpeg", "-hide_banner", "-y", "-nostdin"] + ins +
                ["-filter_complex_script", str(fscript), "-map", "[aout]", "-vn",
                 "-t", f6(P["total"])] + aud + ["-progress", "pipe:1", "-nostats", str(outfile)])
    if A.cpu:
        enc = ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p"]
    else:
        enc = ["-c:v", "h264_nvenc", "-preset", "p1" if A.draft else "p6", "-tune", "hq",
               "-rc", "vbr", "-cq", "28" if A.draft else "19", "-b:v", "0",
               "-maxrate", "80M", "-bufsize", "160M", "-profile:v", "high", "-pix_fmt", "yuv420p"]
    maps = ["-map", f"[{v}]"] + (["-map", f"[{a}]"] + aud if a else ["-an"])
    return (["ffmpeg", "-hide_banner", "-y", "-nostdin"] + ins +
            ["-filter_complex_script", str(fscript)] + maps +
            ["-fps_mode", "cfr", "-r", str(FPS), "-frames:v", str(P["total_frames"]),
             "-t", f6(P["total"])] + enc +
            ["-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(outfile)])


# --- run ------------------------------------------------------------------------------------

def peak_rss(pid):
    """Windows peak working set of one process, MB (0 elsewhere / on failure)."""
    try:
        class C(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_uint32), ("PageFaultCount", ctypes.c_uint32),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        h = ctypes.windll.kernel32.OpenProcess(0x1010, False, pid)
        c = C(); c.cb = ctypes.sizeof(C)
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb)
        ctypes.windll.kernel32.CloseHandle(h)
        return c.PeakWorkingSetSize / 1e6 if ok else 0.0
    except Exception:
        return 0.0


def run(cmd, log, expect_frames):
    """Run ffmpeg, printing a progress line every ~10 s; return (seconds, peak MB)."""
    t0 = time.time(); last = 0.0; peak = 0.0
    with open(log, "wb") as err:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err, text=True, bufsize=1)
        cur = {}
        for line in p.stdout:
            k, _, val = line.strip().partition("=")
            cur[k] = val
            if k == "progress":
                peak = max(peak, peak_rss(p.pid))
                if time.time() - last > 10 or val == "end":
                    el = time.time() - t0
                    fr = int(cur.get("frame", 0) or 0)
                    eta = (expect_frames - fr) / max(1e-6, fr / el) if fr else 0
                    print(f"    {fr}/{expect_frames} frames  fps={cur.get('fps','?')}  "
                          f"speed={cur.get('speed','?')}  {el:.0f}s elapsed  eta {eta:.0f}s  "
                          f"rss {peak:.0f}MB", flush=True)
                    last = time.time()
        p.wait()
    if p.returncode != 0:
        print(f"    FAILED (exit {p.returncode}) - see {log}")
        for ln in open(log, encoding="utf-8", errors="replace").read().splitlines()[-12:]:
            print("      " + ln)
        return None, peak
    return time.time() - t0, peak


def probe(f):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
                          "-show_entries", "stream=nb_read_packets:format=duration",
                          "-of", "json", str(f)], capture_output=True, text=True).stdout
    j = json.loads(out)
    return int(j["streams"][0]["nb_read_packets"]), float(j["format"]["duration"])


def write_cmd(cmd, stem, suffix=""):
    Path(f"{stem}{suffix}.cmd.txt").write_text(
        " ".join(f'"{c}"' if " " in c else c for c in cmd) + "\n", encoding="utf-8")


def parts_of(P, ep, lo, hi, limit):
    """Beat ranges holding at most `limit` shots each, so one ffmpeg run stays small."""
    out, a, count = [], lo, 0
    for bi in range(lo, hi + 1):
        n = len(plan(ep, bi, bi)["shots"])
        if count and count + n > limit:
            out.append((a, bi - 1)); a, count = bi, 0
        count += n
    out.append((a, hi))
    return out


def split_render(P, ep, ldir, outfile, stem):
    """Render each beat range's picture on its own, then join and add one continuous sound track.

    A single graph over a whole 4K episode grows by roughly half a gigabyte per shot - ffmpeg
    reads ahead on every input it has not finished - so long episodes are rendered in parts.
    The parts are joined with -c copy (bit identical, frame exact) and the sound is one pass over
    the whole episode, so the music bed has no seam at a part boundary.
    """
    pdir = outfile.parent / "parts"; pdir.mkdir(exist_ok=True)
    ranges = parts_of(P, ep, P["lo"], P["hi"], A.split)
    print(f"  split into {len(ranges)} parts: " + ", ".join(f"{a}-{b}" for a, b in ranges))
    secs = peak = 0.0
    files, frames = [], 0
    for a, b in ranges:
        Q = plan(ep, a, b)
        f = pdir / f"{stem.name}-p{a}-{b}.mp4"
        cmd = command(Q, ldir, f, Path(f"{f}.filter.txt"), "video")
        write_cmd(cmd, f)
        if not A.dry_run and (A.force or not f.exists()):
            t, pk = run(cmd, Path(f"{f}.log"), Q["total_frames"])
            if t is None:
                sys.exit(1)
            secs += t; peak = max(peak, pk)
        files.append(f); frames += Q["total_frames"]
    au = pdir / f"{stem.name}-audio.m4a"
    cmd = command(P, ldir, au, Path(f"{au}.filter.txt"), "audio")
    write_cmd(cmd, au)
    if A.dry_run:
        print(f"  dry run: {pdir}/*.cmd.txt")
        return None, 0.0
    if A.force or not au.exists():
        t, pk = run(cmd, Path(f"{au}.log"), P["total_frames"])
        if t is None:
            sys.exit(1)
        secs += t; peak = max(peak, pk)
    lst = pdir / f"{stem.name}-parts.txt"
    lst.write_text("".join(f"file '{f.as_posix()}'\n" for f in files), encoding="utf-8")
    join = ["ffmpeg", "-hide_banner", "-y", "-nostdin", "-f", "concat", "-safe", "0", "-i", str(lst),
            "-i", str(au), "-map", "0:v:0", "-map", "1:a:0", "-c", "copy",
            "-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(outfile)]
    write_cmd(join, stem, ".join")
    t, _ = run(join, Path(f"{stem}.join.log"), frames)
    return (secs + t if t is not None else None), peak


def episode(ep):
    lo, hi = (None, None)
    if A.beats:
        a, _, b = A.beats.partition("-")
        lo, hi = int(a), int(b or a)
    P = plan(ep, lo, hi)
    ldir = layers(P)
    print(f"e{ep}: {len(P['shots'])} shots, beats {P['lo']}-{P['hi']}, "
          f"{P['total_frames']} frames = {P['total']:.2f}s ({P['total']/60:.2f} min), "
          f"bed {'yes' if P['bed'] else 'no'}, layers {ldir}")
    if A.layers_only:
        return
    outdir = DRAFTDIR if A.draft else OUTDIR
    outdir.mkdir(parents=True, exist_ok=True)
    tag = f"-b{P['lo']}-{P['hi']}" if A.beats else ""
    name = f"{SLUG}{'' if FILM else '-E' + ep}{tag}{'-draft' if A.draft else ''}.mp4"
    outfile = outdir / name
    stem = outdir / f"e{ep}{tag}{'-draft' if A.draft else ''}"
    chapters = {"episode": ep, "beats": [{"card": r_["card"], "start_seconds": round(r_["start"], 3),
                                          "stamp": r_["stamp"]} for r_ in P["rows"]],
                "total_seconds": round(P["total"], 3), "frames": P["total_frames"]}
    Path(str(stem) + ".chapters.json").write_text(json.dumps(chapters, indent=1, ensure_ascii=False), encoding="utf-8")
    split = A.split and len(P["shots"]) > A.split
    if not split:
        cmd = command(P, ldir, outfile, Path(str(stem) + ".filter.txt"))
        write_cmd(cmd, stem)
    if A.dry_run and not split:
        print(f"  dry run: {stem}.cmd.txt, {stem}.filter.txt")
        return
    if outfile.exists() and not A.force and not A.dry_run:
        print(f"  exists, skipping (use --force): {outfile}")
        return
    if split:
        secs, peak = split_render(P, ep, ldir, outfile, stem)
        if secs is None:
            return
    else:
        secs, peak = run(cmd, Path(str(stem) + ".log"), P["total_frames"])
    if secs is None:
        sys.exit(1)
    frames, dur = probe(outfile)
    ok = frames == P["total_frames"]
    print(f"  {'PASS' if ok else 'FAIL'}  {outfile.name}  {frames} frames "
          f"(expected {P['total_frames']}), {dur:.2f}s, {outfile.stat().st_size/1e6:.0f}MB")
    print(f"  {secs:.0f}s wall = {P['total_frames']/secs:.1f} fps = {P['total']/secs:.2f}x realtime, "
          f"peak rss {peak:.0f}MB")


for ep in [e for e in sorted(EP) if not A.episodes or e in set(A.episodes)]:
    episode(ep)
