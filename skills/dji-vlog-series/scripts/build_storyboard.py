#!/usr/bin/env python3
"""Build a step-4 storyboard beat strip from a hand-authored storyboard-plan.json.

Extracts one real still per source_sample straight from the read-only originals, logs every
extraction in storyboard-provenance.json, writes one eNN-cards.md per episode, and renders a
single self-contained strip.html (stills embedded as base64) for the human gate.

    python build_storyboard.py --plan <review>/storyboard/storyboard-plan.json \
        --source G:/DCIM/DJI_001 --out <review>/storyboard --ffmpeg C:/ffmpeg/bin
"""
import argparse
import base64
import html
import json
import os
import subprocess
import sys

VF = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:-1:-1"
OPERATION = "ffmpeg still extraction; aspect-preserving scale and pad; no color treatment"


def resolve_ffmpeg(arg):
    if os.path.isdir(arg):
        for name in ("ffmpeg.exe", "ffmpeg"):
            cand = os.path.join(arg, name)
            if os.path.exists(cand):
                return cand
        sys.exit("no ffmpeg binary in %s" % arg)
    return arg


def mmss(seconds):
    seconds = int(round(seconds))
    return "%dm %02ds" % (seconds // 60, seconds % 60)


def extract(ffmpeg, original, seconds, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
           "-ss", "%.3f" % seconds, "-i", original, "-frames:v", "1",
           "-vf", VF, "-q:v", "3", dest]
    subprocess.run(cmd, check=True)


def build_stills(plan, source, out, ffmpeg):
    provenance, made, skipped = [], 0, 0
    for ep in plan["proposed_episodes"]:
        for beat in ep["beats"]:
            for s in beat["source_samples"]:
                original = os.path.join(source, s["file"])
                dest = os.path.join(out, s["still"].replace("/", os.sep))
                if os.path.exists(dest):
                    skipped += 1
                else:
                    if not os.path.exists(original):
                        sys.exit("missing original: %s" % original)
                    extract(ffmpeg, original, s["seconds"], dest)
                    made += 1
                provenance.append({"derived": s["still"],
                                   "original": os.path.abspath(original),
                                   "seconds": s["seconds"],
                                   "operation": OPERATION})
    path = os.path.join(out, "storyboard-provenance.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(provenance, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    return made, skipped, path


def card_block(plan, ep, beat):
    runtime = "Proposed %s total — %d%% of %.0f s raw" % (
        mmss(ep["proposed_seconds"]), round(100.0 * ep["proposed_seconds"] / ep["raw_seconds"]),
        ep["raw_seconds"])
    samples = "; ".join("%s @ %.3fs" % (s["file"], s["seconds"]) for s in beat["source_samples"])
    stamp = beat.get("stamp_candidate") or "null (deliberate — no new place in this beat)"
    lines = [
        "## Card %d — Episode %s · %s" % (beat["beat_n"], ep["episode"], beat["title"]),
        "",
        "- status: proposed",
        "- episode: %s" % ep["episode"],
        '- episode_title: "%s"' % ep["tagline"],
        "- beat: %s (%d of %d)" % (beat["position"], beat["beat_n"], beat["of"]),
        "- transition_in: cut",
        '- scene: "%s"' % beat["scene"],
        '- episode_runtime: "%s"' % runtime,
        '- raw_source: "%.1f s raw available for this beat, of %.0f s on the batch"' % (
            beat["raw_seconds_available"], ep["raw_seconds"]),
        '- source_batch: "%s"' % ep["batch"],
        '- source_samples: "%s"' % samples,
        '- coverage: "%s"' % ", ".join(beat["coverage"]),
        '- audio_review: "%s"' % beat["audio_note"],
        '- stamp_candidate: "%s"' % stamp,
        "",
    ]
    return "\n".join(lines)


def build_cards(plan, out):
    written = []
    for ep in plan["proposed_episodes"]:
        head = [
            "# %s — Episode %s cards (proposed)" % (plan["series"], ep["episode"]),
            "",
            "- channel_title: %s" % ep["title"],
            "- batch: %s · %.0f s raw · proposed %s (%d%%)" % (
                ep["batch"], ep["raw_seconds"], mmss(ep["proposed_seconds"]),
                round(100.0 * ep["proposed_seconds"] / ep["raw_seconds"])),
            "- why_this_runtime: %s" % ep["why_this_runtime"],
            "- beats: %d" % len(ep["beats"]),
            "",
            "",
        ]
        body = "\n".join(card_block(plan, ep, b) for b in ep["beats"])
        path = os.path.join(out, "e%s-cards.md" % ep["episode"])
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(head) + body)
        written.append(path)
    return written


def data_uri(path):
    with open(path, "rb") as fh:
        return "data:image/jpeg;base64," + base64.b64encode(fh.read()).decode("ascii")


def build_strip(plan, out):
    e = html.escape
    parts = ["<title>%s — storyboard strip (proposed)</title>" % e(plan["series"]),
             "<style>body{font:14px/1.5 system-ui,sans-serif;margin:0;padding:24px;"
             "background:#14110f;color:#efe9e2}h1{font-size:22px}h2{font-size:18px;"
             "border-top:1px solid #3a332c;padding-top:18px;margin-top:32px}"
             ".card{border:1px solid #3a332c;border-radius:8px;padding:14px;margin:14px 0;"
             "background:#1c1815}.shots{display:flex;gap:8px;flex-wrap:wrap}"
             ".shot{flex:1 1 300px;min-width:0}.shot img{width:100%;border-radius:4px;display:block}"
             ".cap{font:12px monospace;color:#a89c8e;margin-top:4px}"
             "dt{color:#c8a26a;font-weight:600;margin-top:8px}dd{margin:0}"
             ".pos{font:12px monospace;color:#c8a26a}</style>",
             "<h1>%s — proposed beat strip</h1>" % e(plan["series"]),
             "<p>%s · %s · status: <b>proposed, not approved</b></p>" % (
                 e(plan.get("place", "")), e(plan.get("dates", "")))]
    for ep in plan["proposed_episodes"]:
        parts.append("<h2>EP.%s — %s</h2>" % (e(ep["episode"]), e(ep["tagline"])))
        parts.append("<p class=pos>%s · %.0f s raw → proposed %s (%d%%) · %d beats</p>" % (
            e(ep["batch"]), ep["raw_seconds"], mmss(ep["proposed_seconds"]),
            round(100.0 * ep["proposed_seconds"] / ep["raw_seconds"]), len(ep["beats"])))
        parts.append("<p>%s</p>" % e(ep["why_this_runtime"]))
        for beat in ep["beats"]:
            shots = []
            for s in beat["source_samples"]:
                p = os.path.join(out, s["still"].replace("/", os.sep))
                img = ('<img src="%s" alt="">' % data_uri(p)) if os.path.exists(p) else "<i>missing</i>"
                shots.append('<div class=shot>%s<div class=cap>%s @ %.3fs</div></div>' % (
                    img, e(s["file"]), s["seconds"]))
            parts.append(
                '<div class=card><div class=pos>%s · beat %d of %d · %s</div>'
                '<h3>%s</h3><div class=shots>%s</div><dl>'
                '<dt>scene</dt><dd>%s</dd><dt>coverage</dt><dd>%s (%.1f s raw available)</dd>'
                '<dt>audio</dt><dd>%s</dd><dt>stamp candidate</dt><dd>%s</dd></dl></div>' % (
                    e(beat["card"]), beat["beat_n"], beat["of"], e(beat["position"]),
                    e(beat["title"]), "".join(shots), e(beat["scene"]),
                    e(", ".join(beat["coverage"])), beat["raw_seconds_available"],
                    e(beat["audio_note"]), e(beat.get("stamp_candidate") or "null (deliberate)")))
    alt = plan.get("alternative_split") or {}
    if alt:
        parts.append("<h2>Alternative split</h2><p>%s — %s</p>" % (
            e(alt.get("option", "")), e(alt.get("line", ""))))
    path = os.path.join(out, "strip.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser(description="Build storyboard stills, cards and strip.html")
    ap.add_argument("--plan", required=True, help="hand-authored storyboard-plan.json")
    ap.add_argument("--source", required=True, help="read-only originals dir")
    ap.add_argument("--out", required=True, help="storyboard output dir")
    ap.add_argument("--ffmpeg", default="ffmpeg", help="ffmpeg binary or its bin dir")
    args = ap.parse_args()

    with open(args.plan, encoding="utf-8") as fh:
        plan = json.load(fh)

    os.makedirs(args.out, exist_ok=True)
    made, skipped, prov = build_stills(plan, args.source, args.out, resolve_ffmpeg(args.ffmpeg))
    cards = build_cards(plan, args.out)
    strip = build_strip(plan, args.out)
    print("stills extracted: %d (skipped %d already present)" % (made, skipped))
    print("provenance: %s" % prov)
    for c in cards:
        print("cards: %s" % c)
    print("strip: %s" % strip)


if __name__ == "__main__":
    main()
