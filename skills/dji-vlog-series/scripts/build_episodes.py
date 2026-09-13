"""Step 7: build one standalone HyperFrames composition per episode from the reviewed cut lists.

Every project-specific value (paths, canvas, design tokens, episode titles, music beds, series
lines) lives in a JSON config; see templates/series.json. Compositions are GENERATED - change
this file or the config and rerun rather than hand-editing HTML.

  python build_episodes.py --config series.json                     # every episode
  python build_episodes.py --config series.json 04                  # one episode
  python build_episodes.py --config series.json 04 --per-shot       # on per-shot proxies
  python build_episodes.py --config series.json 04 --parts=1-2,3-4  # beat-range parts
  python build_episodes.py --config series.json 04 --suffix=.try2   # write beside, touch nothing

--parts=<beat ranges> writes one composition per range (inclusive, 1-based beats). Each part keeps
the shots, order, durations, proxy sources and stamps of the whole episode; only data-start values
are rebased so the part starts at 0. Part offsets are snapped UP to the joined frame grid, so
sum(part frames) == whole-episode frames and every seam is frame-exact. The music bed gets
data-media-start = the part's absolute offset plus a sliced copy of the whole-episode volume
automation, so the bed is sample-continuous across the seam. The title card appears only in the
part holding beat 1, the end card only in the last part. Join with scripts/join_parts.sh.

Inputs:  <cut_lists>/eNN.json, <frame_index>, <stamps>
Output:  <project>/compositions/episodes/eNN.html (or eNN-partN.html)
"""
import argparse, json, re, html, sys, math
from pathlib import Path

AP = argparse.ArgumentParser()
AP.add_argument("--config", required=True, help="series.json (see templates/series.json)")
AP.add_argument("episodes", nargs="*", help='e.g. 04; empty = every episode in the config')
AP.add_argument("--per-shot", action="store_true")
AP.add_argument("--parts", default="", help="beat ranges, e.g. 1-2,3-4,5-6")
AP.add_argument("--suffix", default="", help="write eNN.html<suffix> and touch nothing else")
A = AP.parse_args()

CFG = json.load(open(A.config, encoding="utf-8"))
CFGDIR = Path(A.config).resolve().parent
def path(key, default=None):
    v = CFG.get(key, default)
    return None if v is None else (CFGDIR / v).resolve()

PROJ = path("project", ".")
CUTS = path("cut_lists")
OUT = PROJ / "compositions" / "episodes"; OUT.mkdir(parents=True, exist_ok=True)
FI = {e["file"]: e for e in json.load(open(path("frame_index"), encoding="utf-8"))}
STAMPS = json.load(open(path("stamps"), encoding="utf-8"))

FPS = CFG.get("fps", 25)
CANVAS_W, CANVAS_H = CFG.get("canvas", [1920, 1080])
VOL = CFG.get("shot_volume", {"keep": 1.0, "duck": 0.6, "music-only": 0.3})
BED_LEVEL = CFG.get("bed_level", {"keep": 0.10, "duck": 0.20, "music-only": 0.45})
BED = CFG.get("bed", {})                       # episode -> bgm file stem
BED_DIR = CFG.get("bed_dir", "assets/bgm")
BED_EXT = CFG.get("bed_ext", ".m4a")
BED_TITLE = CFG.get("bed_title_level", 0.45)
BED_RAMP = CFG.get("bed_ramp", 0.6)
FADE = CFG.get("shot_edge_fade", 0.12)
TITLE_HOLD = CFG.get("title_hold", 4.2)
LABEL_HOLD = CFG.get("stamp_hold", 3.2)
END_HOLD = CFG.get("end_hold", 3.0)
EP = CFG["episodes"]                            # "01": {"title": ..., "batch": ...}
D = CFG.get("design", {})
INK = D.get("ink", "#25302D"); PAPER = D.get("paper", "#F5F1E8")
ACCENT = D.get("accent", "#6A4432"); RULE = D.get("rule", "#C9A88F")
SANS = D.get("sans", '"Montserrat",sans-serif'); MONO = D.get("mono", '"IBM Plex Mono",monospace')
TEXT = CFG.get("text", {})
SERIES_LINE = TEXT.get("series_line", "SERIES · DATE")
FIRST_SERIES_LINE = TEXT.get("first_series_line", SERIES_LINE)
END_LAST = TEXT.get("end_last", "The end.")
END_LAST_SUB = TEXT.get("end_last_sub", SERIES_LINE + " · THE END")
END_SUB_FMT = TEXT.get("end_sub", "{batch} · " + SERIES_LINE)
CREDIT = TEXT.get("credit", "")
PER_SHOT_DIR = CFG.get("per_shot_dir", "assets/clips/<episode>-shots")
PER_SHOT_HANDLE = CFG.get("handle", 1.0)
GSAP = CFG.get("gsap", "assets/gsap.min.js")

PARTS = None
if A.parts:
    PARTS = []
    for seg in A.parts.split(","):
        a, _, b = seg.partition("-")
        PARTS.append((int(a), int(b or a)))

def q(s): return html.escape(str(s), quote=True)
def r(x): return round(x, 3)

def time_of_day(fname):
    """Hour from a camera filename like PREFIX_YYYYMMDDhhmmss_NNNN_D.MP4."""
    m = re.search(r"\d{8}(\d{2})\d{4}", fname)
    h = int(m.group(1)) if m else 12
    return ("morning" if h < 11 else "midday" if h < 14 else
            "afternoon" if h < 17 else "evening" if h < 20 else "night")

def env_value(pts, x):
    """Linear value of the music-bed automation envelope at absolute time x."""
    if x <= pts[0]["t"]: return pts[0]["v"]
    if x >= pts[-1]["t"]: return pts[-1]["v"]
    for i in range(1, len(pts)):
        if pts[i]["t"] >= x:
            t0, v0 = pts[i-1]["t"], pts[i-1]["v"]; t1, v1 = pts[i]["t"], pts[i]["v"]
            return v1 if t1 == t0 else v0 + (v1 - v0) * (x - t0) / (t1 - t0)
    return pts[-1]["v"]

def slice_env(pts, a, b):
    """The whole-episode envelope restricted to [a, b], rebased to 0, with interpolated edges.
    Concatenating every part's slice reproduces the whole-episode bed automation exactly."""
    out = [{"t": 0.0, "v": r(env_value(pts, a))}]
    out += [{"t": r(p["t"] - a), "v": p["v"]} for p in pts if a < p["t"] < b]
    out.append({"t": r(b - a), "v": r(env_value(pts, b))})
    ded = []
    for p in out:
        if ded and abs(p["t"] - ded[-1]["t"]) < 1e-9: ded[-1] = p
        else: ded.append(p)
    return ded

# proxy offsets: the same rule make_proxies.py used, computed across ALL episodes
PROXY_OFFSET = {}
for p in sorted(CUTS.glob("e*.json")):
    if p.stem.endswith("-clips"): continue
    for b in json.load(open(p, encoding="utf-8"))["beats"]:
        for s in b["shots"]:
            PROXY_OFFSET[s["file"]] = min(PROXY_OFFSET.get(s["file"], 1e9), s["in"])
PROXY_OFFSET = {f: max(0.0, v - PER_SHOT_HANDLE) for f, v in PROXY_OFFSET.items()}

def build(ep, per_shot=False, suffix="", part=None):
    d = json.load(open(CUTS / f"e{ep}.json", encoding="utf-8"))
    meta = EP[ep]
    nbeats = len(d["beats"])
    blo, bhi, pidx = (part["lo"], part["hi"], part["idx"]) if part else (1, nbeats, 1)
    off = 0.0            # absolute start time of this part
    part_body_end = 0.0
    pn = 0
    t = 0.0
    vids, auds, labels, tl = [], [], [], []
    n = 0
    env = []
    first_shot_len = None
    first_stamp = ""
    shot_dir = PER_SHOT_DIR.replace("<episode>", f"e{ep}")
    for bi, beat in enumerate(d["beats"], 1):
        beat_start = t
        # a part starts at its first beat, snapped up to the joined frame grid (part["off"],
        # <frames rendered so far>/fps) so the concatenated parts stay frame-exact
        if part and bi == blo: off = part.get("off", beat_start)
        inpart = blo <= bi <= bhi
        for s in beat["shots"]:
            n += 1
            f = s["file"]; stem = Path(f).stem
            if per_shot:
                lo = max(0.0, s["in"] - PER_SHOT_HANDLE)
                src = f"{shot_dir}/{stem}__s{n:02d}.mp4"
            else:
                lo = PROXY_OFFSET[f]
                src = f"assets/clips/{stem}.mp4"
            ms = r(s["in"] - lo); dur = r(s["out"] - s["in"])
            if inpart and first_shot_len is None: first_shot_len = dur
            # max(0,...) only bites on a part's first element, whose off is snapped up by < 1 frame
            rt = r(max(0.0, t - off))
            vid = (f'<video id="v{n}" class="clip" src="{src}" data-start="{rt}" '
                   f'data-duration="{dur}" data-media-start="{ms}" data-track-index="0" muted playsinline></video>')
            vol = VOL.get(s.get("audio", "keep"), 1.0)
            aud = (f'<audio id="a{n}" src="{src}" data-start="{rt}" data-duration="{dur}" '
                   f'data-media-start="{ms}" data-track-index="{10 + (n % 2)}"></audio>')
            if inpart:
                pn += 1
                vids.append(vid); auds.append(aud)
            env.append((t, BED_LEVEL.get(s.get("audio", "keep"), 0.10)))
            fd = min(FADE, dur / 3)                       # edge fades so hard cuts do not click
            if inpart:
                tl.append(f'tl.fromTo("#a{n}",{{volume:0}},{{volume:{vol},duration:{fd},ease:"none"}},{rt});')
                tl.append(f'tl.to("#a{n}",{{volume:0,duration:{fd},ease:"none"}},{r(t + dur - fd - off)});')
            t += dur
        if part and bi == bhi: part_body_end = t
        place = STAMPS.get(beat["card"])
        tod = time_of_day(beat["shots"][0]["file"])
        text = f"{place} · {tod}" if place else tod.capitalize()
        if bi > 1:                                        # beat 1 waits for the title to clear
            if inpart:
                rs = r(max(0.0, beat_start - off))
                labels.append(f'<div id="lb{bi}" class="clip label" data-start="{rs}" '
                              f'data-duration="{LABEL_HOLD}" data-track-index="2">{q(text)}</div>')
                tl.append(f'tl.fromTo("#lb{bi}",{{opacity:0,y:8}},{{opacity:1,y:0,duration:0.5,ease:"power2.out"}},{rs});')
                tl.append(f'tl.to("#lb{bi}",{{opacity:0,duration:0.5,ease:"power2.in"}},{r(beat_start + LABEL_HOLD - 0.5 - off)});')
        else:
            first_stamp = text
    body_end = t
    hold = min(TITLE_HOLD, max(2.5, (first_shot_len or TITLE_HOLD) - 0.3))
    total = body_end + END_HOLD

    # bed envelope: title level, then per-shot levels with short ramps, fading over the end card
    pts = [{"t": 0, "v": BED_TITLE}]
    last = BED_TITLE
    for (st, lv) in env:
        if abs(lv - last) < 1e-6: continue
        if st > 0: pts.append({"t": r(max(0, st - BED_RAMP / 2)), "v": last})
        pts.append({"t": r(st + BED_RAMP / 2), "v": lv}); last = lv
    pts.append({"t": r(body_end), "v": last}); pts.append({"t": r(total - 0.2), "v": 0.0})
    pts = [p for i, p in enumerate(pts) if i == 0 or p["t"] >= pts[i-1]["t"]]

    is_last_part = (bhi == nbeats)
    show_title = (blo == 1)
    show_end = is_last_part
    out_body_end = r(part_body_end - off) if part else body_end
    out_total = r(out_body_end + END_HOLD) if (part and show_end) else (out_body_end if part else total)
    bed_pts = slice_env(pts, off, off + out_total) if part else pts
    bed_ms = r(off) if part else 0

    auto = json.dumps({"version": 1, "lanes": [{"target": "volume", "points": bed_pts}]})
    bed_src = f"{BED_DIR}/{BED.get(ep, '')}{BED_EXT}"
    bed = ('<audio id="bed" src="' + bed_src + '" data-start="0" data-duration="' + str(r(out_total)) +
           '" data-media-start="' + str(bed_ms) + '" data-track-index="12" data-volume="1" '
           "data-automation='" + auto + "'></audio>") if BED.get(ep) else ""
    if bed: auds.append(bed)

    order = sorted(EP)
    is_first = ep == order[0]; is_last = ep == order[-1]
    series_line = FIRST_SERIES_LINE if is_first else SERIES_LINE
    end_text = END_LAST if is_last else f"Episode {int(ep):02d}"
    end_sub = END_LAST_SUB if is_last else END_SUB_FMT.format(batch=meta.get("batch", ""), ep=int(ep))

    title_html = f'''<div id="titlewrap" class="clip" data-start="0" data-duration="{r(hold)}" data-track-index="1">
  <div id="scrim"></div>
  <div id="title">
    <div class="eyebrow">{q(series_line)}</div>
    <h1>{q(meta["title"])}</h1>
    <div class="sub">EPISODE {int(ep):02d} · {q(meta.get("batch",""))} · {q(first_stamp.upper())}</div>
  </div>
</div>''' if show_title else ""
    end_html = f'''<div id="end" class="clip" data-start="{r(out_body_end)}" data-duration="{END_HOLD}" data-track-index="1">
  <div class="big">{end_text}</div>
  <div class="small">{q(end_sub)}</div>
  <div class="credit">{q(CREDIT)}</div>
</div>''' if show_end else ""
    tl_head = []
    if show_title:
        tl_head.append('tl.fromTo("#titlewrap",{opacity:0},{opacity:1,duration:0.7,ease:"power2.out"},0);')
        tl_head.append(f'tl.to("#titlewrap",{{opacity:0,duration:0.6,ease:"power2.in"}},{r(hold - 0.6)});')
    if show_end:
        tl_head.append(f'tl.fromTo("#end",{{opacity:0}},{{opacity:1,duration:0.8,ease:"power2.inOut"}},{r(out_body_end)});')
    comp_id = f"e{ep}-part{pidx}" if part else f"e{ep}"

    page = f'''<!DOCTYPE html>
<html lang="{CFG.get("lang","en")}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={CANVAS_W}, height={CANVAS_H}">
<script src="{GSAP}"></script>
<style>
html,body{{margin:0;width:{CANVAS_W}px;height:{CANVAS_H}px;overflow:hidden;background:#000;}}
#root{{position:absolute;inset:0;width:{CANVAS_W}px;height:{CANVAS_H}px;overflow:hidden;background:#000;color:{PAPER};font-family:{SANS};}}
.clip{{position:absolute;inset:0;}}
#titlewrap{{opacity:0;}}
video.clip{{width:{CANVAS_W}px;height:{CANVAS_H}px;object-fit:contain;background:#000;}}
#scrim{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,0) 55%,rgba(0,0,0,.55) 100%);pointer-events:none;}}
#title{{position:absolute;inset:auto auto 92px 96px;width:1400px;}}
#title .eyebrow{{font:400 26px {MONO};letter-spacing:4px;color:{PAPER};opacity:.85;margin-bottom:14px;}}
#title h1{{margin:0;font-size:88px;font-weight:700;line-height:1.05;letter-spacing:-2.5px;text-shadow:0 2px 24px rgba(0,0,0,.35);}}
#title .sub{{margin-top:16px;font:400 28px {MONO};letter-spacing:3px;opacity:.9;}}
.label{{opacity:0;position:absolute;inset:auto auto 84px 96px;width:auto;height:auto;font:400 26px {MONO};letter-spacing:2px;color:{PAPER};padding:10px 0 0 0;border-top:2px solid {RULE};text-shadow:0 1px 14px rgba(0,0,0,.55),0 0 2px rgba(0,0,0,.6);}}
#end{{opacity:0;position:absolute;inset:0;background:{PAPER};color:{INK};display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;}}
#end .big{{font-size:64px;font-weight:700;line-height:1.15;letter-spacing:-1.5px;max-width:1500px;}}
#end .credit{{position:absolute;left:0;right:0;bottom:44px;font:400 18px {MONO};letter-spacing:3px;color:{ACCENT};opacity:.7;}}
#end .small{{margin-top:28px;font:400 26px {MONO};letter-spacing:4px;color:{ACCENT};}}
</style>
</head>
<body>
<div id="root" data-composition-id="{comp_id}" data-start="0" data-duration="{r(out_total)}" data-width="{CANVAS_W}" data-height="{CANVAS_H}" data-fps="{FPS}">
{chr(10).join(vids)}
{title_html}
{chr(10).join(labels)}
{end_html}
{chr(10).join(auds)}
</div>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{paused:true}});
{chr(10).join(tl_head)}
{chr(10).join(tl)}
window.__timelines["{comp_id}"] = tl;
</script>
</body>
</html>
'''
    dst = OUT / (f"e{ep}-part{pidx}.html{suffix}" if part else f"e{ep}.html{suffix}")
    dst.write_text(page, encoding="utf-8")
    return (pn if part else n), (out_total if part else total), dst

targets = [e for e in sorted(EP) if not A.episodes or e in set(A.episodes)]

if PARTS:
    if len(targets) != 1:
        sys.exit("--parts needs exactly one episode, e.g. build_episodes.py --config c.json 04 --parts=1-2,3-4")
    ep = targets[0]
    joined = 0
    for i, (a, b) in enumerate(PARTS, 1):
        n, tot, dst = build(ep, per_shot=A.per_shot, suffix=A.suffix,
                            part={"lo": a, "hi": b, "idx": i, "cnt": len(PARTS), "off": r(joined / FPS)})
        frames = math.ceil(round(tot * FPS, 6))
        joined += frames
        tail = (f", seam after this part at joined frame {joined} (t={joined/FPS:.2f}s)"
                if i < len(PARTS) else f", joined total {joined} frames = {joined/FPS:.2f}s")
        print(f"{dst.name}: beats {a}-{b}, {n} shots, {tot:.2f}s ({tot/60:.2f} min), {frames} frames{tail}"
              + ("  [per-shot proxies]" if A.per_shot else ""))
    print(f"\njoin with: sh join_parts.sh {ep} {len(PARTS)} --total {joined} --seams <seam frames>")
    sys.exit(0)

summary = []
for ep in targets:
    n, total, dst = build(ep, per_shot=A.per_shot, suffix=A.suffix)
    summary.append((ep, n, total))
    print(f"e{ep}{A.suffix}: {n} shots, {total/60:.2f} min ({total:.1f}s)"
          + ("  [per-shot proxies]" if A.per_shot else ""))
if not A.episodes and not A.suffix:
    json.dump({e: {"shots": n, "seconds": round(t, 2), "frames": math.ceil(round(t * FPS, 6))}
               for e, n, t in summary}, open(OUT / "_summary.json", "w"), indent=1)
