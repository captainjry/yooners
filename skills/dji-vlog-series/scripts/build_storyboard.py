#!/usr/bin/env python3
"""Build a step-4 storyboard beat strip from a hand-authored storyboard-plan.json.

Extracts one real still per source_sample straight from the read-only originals, logs every
extraction in storyboard-provenance.json, writes one eNN-cards.md per episode, and renders a
single self-contained strip.html (stills embedded as base64) for the human gate.

    python build_storyboard.py --plan <review>/storyboard/storyboard-plan.json \
        --source G:/DCIM/DJI_001 --out <review>/storyboard --ffmpeg C:/ffmpeg/bin

Add --hf-frames <project dir> to instead (or additionally) turn the plan into one HyperFrames
frame composition per beat under <project dir>/compositions/frames, plus a STORYBOARD.md in the
Studio's STORYBOARD.md format, reading stills from <project dir>/assets/storyboard (already
extracted/copied there — this mode does not touch ffmpeg or --source). Header fields
(message, audience, arc, date_labels) come from the plan's top level:

    python build_storyboard.py --plan <project>/storyboard-plan.json --hf-frames <project>
"""
import argparse
import base64
import html
import json
import os
import re
import random
import subprocess
import sys

VF = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:-1:-1"
OPERATION = "ffmpeg still extraction; aspect-preserving scale and pad; no color treatment"

# --- HyperFrames frame-card generation (--hf-frames) --------------------------------------

CLIP_NUM_RE = re.compile(r"_(\d{4})_[A-Za-z]\.[Mm][Pp]4$")
HFID_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"

# The channel's card layout from the first series, plus one additive
# .meta rule for the audio-note / stamp-candidate line.
HF_CARD_CSS = """
#root {position:absolute;inset:0;width:1920px;height:1080px;overflow:hidden;background:#F5F1E8;color:#25302D;font-family:"Montserrat",sans-serif;}
#root * {box-sizing:border-box;} #root .eyebrow {position:absolute;left:64px;top:38px;font:400 24px "IBM Plex Mono",monospace;letter-spacing:2px;color:#6A4432;}
#root h1 {position:absolute;left:60px;top:68px;margin:0;font-size:64px;font-weight:700;line-height:1.12;letter-spacing:-2px;}
#root .timing {position:absolute;right:64px;top:44px;text-align:right;font:400 24px "IBM Plex Mono",monospace;}
#root figure {margin:0;position:absolute;background:#25302D;overflow:hidden;} #root img {width:100%;height:100%;object-fit:contain;display:block;}
#root .hero {left:60px;top:176px;width:1196px;height:672px;} #root .support {left:1280px;width:580px;height:326px;} #root .support-1 {top:176px;} #root .support-2 {top:522px;}
#root figcaption {position:absolute;left:0;bottom:0;padding:7px 13px;background:#F5F1E8;color:#25302D;font:400 22px "IBM Plex Mono",monospace;}
#root .intent {position:absolute;left:64px;top:876px;width:1750px;margin:0;font-size:32px;line-height:1.42;font-weight:400;}
#root .footer {position:absolute;left:64px;bottom:31px;font:400 21px "IBM Plex Mono",monospace;color:#6A4432;}
#root .meta {position:absolute;left:64px;width:1750px;margin:0;font:400 13px "IBM Plex Mono",monospace;color:#6A4432;line-height:1.15;overflow:hidden;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;}
""".strip("\n")

# Per-card inline overrides on .intent (scene text length varies a lot between series) so the
# shared class rule above stays untouched while every card still fits the 1920x1080 frame above
# the footer.
INTENT_INLINE = ("top:862px;height:96px;overflow:hidden;font-size:24px;line-height:1.28;"
                  "display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;")
META_TOP = 970
META_HEIGHT = 34


def clip_number(filename):
    m = CLIP_NUM_RE.search(filename)
    return m.group(1) if m else filename


def hf_id(rng):
    return "hf-" + "".join(rng.choice(HFID_CHARS) for _ in range(4))


def still_project_path(still_field):
    """Map a plan `still` value (any `.../<name>.jpg`) onto the project's assets/storyboard/<name>.jpg."""
    return "assets/storyboard/" + os.path.basename(still_field)


def figure_html(rng, cls, sample):
    num = clip_number(sample["file"])
    seconds = sample["seconds"]
    src = still_project_path(sample["still"])
    return (
        '<figure data-hf-id="%s" class="%s"><img data-hf-id="%s" src="%s" '
        'alt="%s source still at %.2fs"><figcaption data-hf-id="%s">%s / %.2fs</figcaption></figure>'
        % (hf_id(rng), cls, hf_id(rng), html.escape(src, quote=True),
           html.escape(sample["file"]), seconds, hf_id(rng), num, seconds)
    )


def frame_card_html(ep, beat):
    rng = random.Random("hf-frame:" + beat["card"])
    mm = mmss(ep["proposed_seconds"])
    eyebrow = "EPISODE %s / %s SOURCE BATCH / 2026" % (ep["episode"], ep["batch"].upper())
    samples = beat["source_samples"]
    hero = figure_html(rng, "hero", samples[0])
    supports = []
    if len(samples) > 1:
        supports.append(figure_html(rng, "support support-1", samples[1]))
    if len(samples) > 2:
        supports.append(figure_html(rng, "support support-2", samples[2]))

    stamp = beat.get("stamp_candidate") or "none (deliberate — no new place in this beat)"
    meta_text = "AUDIO \u2014 %s   STAMP \u2014 %s" % (beat["audio_note"], stamp)

    comp_id = beat["card"]
    lines = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8"></head><body><template>',
        "<style>",
        HF_CARD_CSS,
        "</style>",
        '<div data-hf-id="%s" id="root" data-composition-id="%s" data-width="1920" data-height="1080" data-duration="3">'
        % (hf_id(rng), comp_id),
        '<div data-hf-id="%s" class="eyebrow">%s</div><h1 data-hf-id="%s">%s</h1>'
        % (hf_id(rng), html.escape(eyebrow), hf_id(rng), html.escape(beat["title"])),
        '<div data-hf-id="%s" class="timing">EPISODE %s<p data-hf-id="%s" style="margin:6px 0 0">PROPOSED %s \u00b7 BEAT %d OF %d</p></div>'
        % (hf_id(rng), ep["episode"], hf_id(rng), mm, beat["beat_n"], beat["of"]),
        hero,
        "".join(supports),
        '<p data-hf-id="%s" class="intent" style="%s">%s</p>'
        % (hf_id(rng), INTENT_INLINE, html.escape(beat["scene"])),
        '<p data-hf-id="%s" class="meta" style="top:%dpx;height:%dpx">%s</p>'
        % (hf_id(rng), META_TOP, META_HEIGHT, html.escape(meta_text)),
        '<div data-hf-id="%s" class="footer">STORYBOARD EVIDENCE / ORIGINAL SOURCE STILLS / NOT THE FINAL EDIT</div>'
        % hf_id(rng),
        "</div><script>window.__timelines[\"%s\"] = gsap.timeline({paused:true});</script>" % comp_id,
        "</template></body></html>",
    ]
    return "\n".join(lines) + "\n"


def build_hf_frames(plan, project_dir):
    frames_dir = os.path.join(project_dir, "compositions", "frames")
    os.makedirs(frames_dir, exist_ok=True)
    written = []
    for ep in plan["proposed_episodes"]:
        for beat in ep["beats"]:
            path = os.path.join(frames_dir, "%s.html" % beat["card"])
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(frame_card_html(ep, beat))
            written.append(path)
    return written


def storyboard_md(plan):
    episodes = plan["proposed_episodes"]
    total_cards = sum(len(ep["beats"]) for ep in episodes)
    ep_summary = " \u00b7 ".join(
        "%s %s (%s, %s)" % (ep["episode"], ep["tagline"], ep["batch"], mmss(ep["proposed_seconds"]))
        for ep in episodes
    )
    front = [
        "---",
        "format: 1920x1080",
        'duration: "%s"' % " \u00b7 ".join(
            "EP.%s %s (%s)" % (ep["episode"], mmss(ep["proposed_seconds"]), ep["batch"]) for ep in episodes),
        'message: "%s"' % plan.get("message", "<set message in storyboard-plan.json>"),
        'arc: "%s"' % plan.get("arc", "<set arc in storyboard-plan.json: the series in two sentences>"),
        'audience: "%s"' % plan.get("audience", "The friends who travelled together"),
        "mode: collaborative",
        'date_labels: "%s"' % plan.get("date_labels", "Filename-date source batches only; place names "
                                        "withheld where not legible on screen or said on camera."),
        'runtime_basis: "Provisional editorial targets from indexed coverage and raw source runtime per '
        'filename date. Exact trims, dialogue, and usable action require motion-and-audio review after '
        'storyboard approval."',
        'approval: "Storyboard proposed — cards built as HyperFrames frames at compositions/frames by '
        'tools/build_storyboard.py --hf-frames from storyboard-plan.json. Not yet approved. No renders '
        'started."',
        'board_shape: "One card per episode beat: open, middle beats, a close. %d cards across %d '
        'episodes."' % (total_cards, len(episodes)),
        'episodes: "%s"' % ep_summary,
        "---",
        "",
    ]

    body = []
    n = 0
    for ep in episodes:
        for beat in ep["beats"]:
            n += 1
            samples = "; ".join("%s @ %.3fs" % (s["file"], s["seconds"]) for s in beat["source_samples"])
            stamp = beat.get("stamp_candidate") or "null (deliberate — no new place in this beat)"
            body += [
                "## Frame %d — Episode %s \u00b7 %s" % (n, ep["episode"], beat["title"]),
                "",
                "- status: built",  # Studio storyboard page shows the card only when built + src
                "- src: compositions/frames/%s.html" % beat["card"],
                "- episode: %s" % ep["episode"],
                '- episode_title: "%s"' % ep["tagline"],
                "- beat: %s (%d of %d)" % (beat["position"], beat["beat_n"], beat["of"]),
                "- transition_in: cut",
                '- scene: "%s"' % beat["scene"],
                '- episode_runtime: "Proposed %s total"' % mmss(ep["proposed_seconds"]),
                '- raw_source: "%.1f min raw across the %s filename batch"' % (
                    ep["raw_seconds"] / 60.0, ep["batch"]),
                '- source_batch: "%s"' % ep["batch"],
                '- source_samples: "%s"' % samples,
                '- audio_review: "%s"' % beat["audio_note"],
                '- stamp_candidate: "%s"' % stamp,
                "",
            ]
    return "\n".join(front) + "\n" + "\n".join(body)


def build_storyboard_md(plan, project_dir):
    path = os.path.join(project_dir, "STORYBOARD.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(storyboard_md(plan))
    return path


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
        "- src: compositions/frames/%s.html (not built)" % beat["card"],
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
    ap.add_argument("--source", help="read-only originals dir (required unless only --hf-frames is used)")
    ap.add_argument("--out", help="storyboard output dir (required unless only --hf-frames is used)")
    ap.add_argument("--ffmpeg", default="ffmpeg", help="ffmpeg binary or its bin dir")
    ap.add_argument("--hf-frames", metavar="PROJECT_DIR",
                     help="also/instead write one HyperFrames frame composition per beat under "
                          "PROJECT_DIR/compositions/frames (stills read from "
                          "PROJECT_DIR/assets/storyboard, expected already present), plus "
                          "PROJECT_DIR/STORYBOARD.md")
    args = ap.parse_args()

    with open(args.plan, encoding="utf-8") as fh:
        plan = json.load(fh)

    if args.source or args.out:
        if not (args.source and args.out):
            sys.exit("--source and --out must be given together")
        os.makedirs(args.out, exist_ok=True)
        made, skipped, prov = build_stills(plan, args.source, args.out, resolve_ffmpeg(args.ffmpeg))
        cards = build_cards(plan, args.out)
        strip = build_strip(plan, args.out)
        print("stills extracted: %d (skipped %d already present)" % (made, skipped))
        print("provenance: %s" % prov)
        for c in cards:
            print("cards: %s" % c)
        print("strip: %s" % strip)

    if args.hf_frames:
        frames = build_hf_frames(plan, args.hf_frames)
        for f in frames:
            print("frame: %s" % f)
        sb = build_storyboard_md(plan, args.hf_frames)
        print("storyboard: %s" % sb)

    if not (args.source or args.out or args.hf_frames):
        sys.exit("nothing to do: pass --source/--out, --hf-frames, or both")


if __name__ == "__main__":
    main()
