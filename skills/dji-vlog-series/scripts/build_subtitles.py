"""Step 8: subtitle sidecars (SRT) per episode, remapped from the source transcripts through the cut.

Sidecars, not burned-in: YouTube can then translate them and the picture stays clean.

  python build_subtitles.py --cut-lists <review>/clip-review --transcripts <review>/transcripts \
      --out <project>/renders/subtitles --lang th --fix "wrong phrase=>right phrase"

Output: <out>/eNN.<lang>.srt (UTF-8 with BOM, which is what YouTube and most players expect).

Rules, in order: keep only speech inside a kept shot range; drop segments with
no_speech_prob > --max-no-speech; drop degenerate repeats (ASR hallucinations); apply the fix
list; split cues over --max-cue on word timestamps; merge sub-0.7 s cues into their predecessor;
enforce a 1 s minimum display with no overlap. Shots marked audio "music-only" carry no cues.
"""
import argparse, json, re
from pathlib import Path

AP = argparse.ArgumentParser()
AP.add_argument("--cut-lists", required=True)
AP.add_argument("--transcripts", required=True)
AP.add_argument("--out", required=True)
AP.add_argument("--lang", default="th")
AP.add_argument("--max-cue", type=float, default=6.0)
AP.add_argument("--max-no-speech", type=float, default=0.6)
AP.add_argument("--max-chars", type=int, default=70)
AP.add_argument("--fix", action="append", default=[], help='"<regex>=>replacement", repeatable')
A = AP.parse_args()

OUT = Path(A.out); OUT.mkdir(parents=True, exist_ok=True)
FIXES = [tuple(f.split("=>", 1)) for f in A.fix if "=>" in f]

def ts(x):
    ms = int(round(x * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def degenerate(text):
    toks = text.split()
    return (len(toks) >= 4 and len(set(toks)) <= 2) or bool(re.fullmatch(r"(.)\1{5,}", text.replace(" ", "")))

total = 0
for p in sorted(Path(A.cut_lists).glob("e??.json")):
    d = json.load(open(p, encoding="utf-8")); ep = d["episode"]
    t = 0.0; cues = []
    for beat in d["beats"]:
        for s in beat["shots"]:
            dur = s["out"] - s["in"]
            if s.get("audio") != "music-only":
                tr = json.load(open(Path(A.transcripts) / (Path(s["file"]).stem + ".json"), encoding="utf-8"))
                for seg in tr["segments"]:
                    if seg["no_speech_prob"] > A.max_no_speech or degenerate(seg["text"]): continue
                    a, b = max(seg["start"], s["in"]), min(seg["end"], s["out"])
                    if b - a < 0.4: continue
                    text = seg["text"].strip()
                    for pat, rep in FIXES: text = re.sub(pat, rep, text, flags=re.I)
                    words = [w for w in seg.get("words", []) if s["in"] <= w["s"] < s["out"]]
                    if b - a > A.max_cue and len(words) > 6:
                        n = int((b - a) // A.max_cue) + 1; chunk = max(1, len(words) // n)
                        for i in range(0, len(words), chunk):
                            ws = words[i:i+chunk]
                            cues.append((t + ws[0]["s"] - s["in"],
                                         t + min(ws[-1]["e"], s["out"]) - s["in"],
                                         "".join(w["w"] for w in ws).strip()))
                    elif b - a > A.max_cue:
                        # few/no word timestamps: clamp a long cue to max_cue from its start
                        # (fix 2026-09-11: sparse-word segments escaped the max_cue rule)
                        cues.append((t + a - s["in"], t + a + A.max_cue - s["in"], text))
                    else:
                        cues.append((t + a - s["in"], t + b - s["in"], text))
            t += dur
    cues = [c for c in cues if c[2]]
    fixed = []
    for a, b, text in cues:
        if len(text) <= A.max_chars: fixed.append((a, b, text)); continue
        parts = text.split(" "); n = (len(text) // (A.max_chars - 10)) + 1; k = max(1, len(parts) // n)
        chunks = [" ".join(parts[i:i+k]) for i in range(0, len(parts), k)]
        step = (b - a) / len(chunks)
        fixed += [(a + i*step, a + (i+1)*step, c) for i, c in enumerate(chunks)]
    cues = sorted(fixed)
    merged = []
    for a, b, text in cues:
        if merged and b - a < 0.7 and a - merged[-1][1] < 0.3 and len(merged[-1][2]) + len(text) < A.max_chars:
            pa, pb, pt = merged[-1]; merged[-1] = (pa, max(pb, b), pt + " " + text)
        else: merged.append((a, b, text))
    # 1 s minimum without overlap: if the next cue starts too soon, merge into it
    # (fix 2026-09-11: the no-overlap clamp used to override the 1 s floor)
    i = 0; squashed = []
    while i < len(merged):
        a, b, text = merged[i]
        while i + 1 < len(merged) and merged[i+1][0] - 0.05 < a + 1.0 and len(text) + len(merged[i+1][2]) < A.max_chars * 2:
            i += 1; b = max(b, merged[i][1]); text = text + " " + merged[i][2]
        squashed.append((a, b, text)); i += 1
    cues = []
    for i, (a, b, text) in enumerate(squashed):
        b = max(b, a + 1.0)
        if i + 1 < len(squashed): b = min(b, squashed[i+1][0] - 0.05)
        if b > a: cues.append((a, b, text))
    with open(OUT / f"e{ep}.{A.lang}.srt", "w", encoding="utf-8-sig") as f:
        for i, (a, b, text) in enumerate(cues, 1):
            f.write(f"{i}\n{ts(a)} --> {ts(b)}\n{text}\n\n")
    total += len(cues); print(f"e{ep}: {len(cues)} cues")
print("total", total)
