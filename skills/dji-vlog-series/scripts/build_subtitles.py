"""Step 7: subtitle sidecars (SRT) per episode, remapped from the source transcripts through the cut.

Sidecars, not burned-in: YouTube can then translate them and the picture stays clean.

  python build_subtitles.py --config <project>/series.json --transcripts <review>/transcripts \
      --out <project>/renders/subtitles

Output: <out>/eNN.<lang>.srt (UTF-8 with BOM, which is what YouTube and most players expect).

Everything about one series comes from the `subtitles` block of series.json (see
templates/series.json); this file holds no language, place or project of its own:
  speech_script  script the speech is written in ("thai", "kana", ...; "" for Latin-script speech)
  drop_scripts   scripts that never occur in this footage, so a cue containing one is an ASR
                 hallucination and is dropped (e.g. ["cyrillic", "latin-ext"])
  keep_words     Latin words that are real when glued onto the speech script (place names,
                 loanwords); the Latin words of every place stamp are added automatically
  fixes          {"wrong regex": "right"} for the series' known ASR errors
  max_cue / max_no_speech / max_chars
A flag on the command line overrides the same key in the config.

Rules, in order: keep only speech inside a kept shot range; drop segments with
no_speech_prob > max_no_speech; drop degenerate repeats (repeated-token runs, a repeated
character) and cues containing a drop_scripts character. When speech_script is set, a token that
glues it onto a Latin run outside keep_words loses just that token, and the cue is dropped only if
fewer than 2 speech-script characters remain. Then apply the fixes; split cues over max_cue on word
timestamps; merge sub-0.7 s cues into their predecessor; enforce a 1 s minimum display with no
overlap. Shots marked audio "music-only" or "subtitles": false carry no cues. --selftest runs
inline synthetic checks and exits, touching no project files.
"""
import argparse, json, re
from pathlib import Path

AP = argparse.ArgumentParser()
AP.add_argument("--config", help="series.json; supplies cut_lists, stamps, lang and the subtitles block")
AP.add_argument("--cut-lists")
AP.add_argument("--transcripts")
AP.add_argument("--out")
AP.add_argument("--lang")
AP.add_argument("--max-cue", type=float)
AP.add_argument("--max-no-speech", type=float)
AP.add_argument("--max-chars", type=int)
AP.add_argument("--fix", action="append", default=[], help='"<regex>=>replacement", repeatable; added to the config fixes')
AP.add_argument("--stamps", default=None, help="stamps.json when not given by --config")
AP.add_argument("--selftest", action="store_true", help="run inline synthetic self-checks and exit (no file I/O)")
A = AP.parse_args()

SCRIPTS = {
    "thai": "\u0e00-\u0e7f", "cyrillic": "\u0400-\u04ff", "latin-ext": "\u00c0-\u024f",
    "kana": "\u3040-\u30ff", "cjk": "\u4e00-\u9fff", "hangul": "\uac00-\ud7af",
    "arabic": "\u0600-\u06ff", "devanagari": "\u0900-\u097f",
}
LATIN_RUN = re.compile(r"[A-Za-z]+")

def script_re(names):
    names = [names] if isinstance(names, str) else list(names or [])
    unknown = [n for n in names if n and n not in SCRIPTS]
    if unknown: raise SystemExit(f"unknown script {unknown}; known: {sorted(SCRIPTS)}")
    ranges = "".join(SCRIPTS[n] for n in names if n)
    return re.compile(f"[{ranges}]") if ranges else None

class Rules:
    """The per-series cleaning rules, built from the `subtitles` block."""
    def __init__(self, speech_script="", drop_scripts=(), keep_words=(), stamps=None):
        self.speech = script_re(speech_script)
        self.drop = script_re(drop_scripts)
        self.keep = {w.lower() for w in keep_words}
        for v in (stamps or {}).values():
            if isinstance(v, str): self.keep.update(w.lower() for w in LATIN_RUN.findall(v))

def ts(x):
    ms = int(round(x * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def strip_mixed_tokens(text, rules):
    # A speech-script+Latin token glued into one word, where the Latin run isn't a kept word,
    # is an ASR hallucination fused onto real speech -- strip just that token. Standalone
    # Latin tokens, single letters and bare numbers are never touched.
    kept = []; dropped_any = False
    for tok in text.split():
        if rules.speech.search(tok) and any(len(run) > 1 and run.lower() not in rules.keep
                                            for run in LATIN_RUN.findall(tok)):
            dropped_any = True
            continue  # drop only this token
        kept.append(tok)
    if not dropped_any: return text  # nothing to strip -- leave untouched
    result = " ".join(kept)
    if len(rules.speech.findall(result)) < 2: return None  # nothing real left -> drop the cue
    return result

def degenerate(text, rules):
    """Returns the (possibly cleaned) cue text to keep, or None to drop the cue entirely."""
    toks = text.split()
    if (len(toks) >= 4 and len(set(toks)) <= 2) or bool(re.fullmatch(r"(.)\1{5,}", text.replace(" ", ""))):
        return None
    if rules.drop and rules.drop.search(text):
        return None
    if rules.speech:
        text = strip_mixed_tokens(text, rules)
    return text

def run_selftest():
    # a Thai series shot abroad: Cyrillic / diacritic-Latin never occur, Japanese does
    th = Rules("thai", ["cyrillic", "latin-ext"], ["Lake", "Sunset", "ski", "sky", "Biei"])
    th_stamps = Rules("thai", ["cyrillic", "latin-ext"], ["Sunset"], {"e01-3": "Lake Shikotsu"})
    for bad in ["людям то же самое", "Hú, csomára jön!", "Neverée Geido", "ถ้า ко"]:
        assert degenerate(bad, th) is None, f"drop_scripts missed: {bad!r}"
    for good in ["アザラシは後ろ足で泳ぎます", "次は小樽駅前行きです"]:
        assert degenerate(good, th) == good, f"script outside drop_scripts wrongly dropped: {good!r}"
    stripped = degenerate("บุคaiserอะไร กูลืมชื่ออีกแล้ว.. สวยมาก", th)
    assert stripped == "กูลืมชื่ออีกแล้ว.. สวยมาก", f"strip failed: {stripped!r}"
    assert degenerate("อันนี้มันจะมีILLFARMในใจ", th) is None, "single-token mixed cue should drop"
    for good in ["พรุ่งนี้ไปsky กัน", "สนุกมากตอนไปski", "ถ้าใครมาก็แนะนำรอให้Sunset ก่อน"]:
        assert degenerate(good, th) == good, f"keep_words ignored: {good!r}"
    assert degenerate("อันนี้เราไปLake Shikotsu นะ", th_stamps) == "อันนี้เราไปLake Shikotsu นะ", "stamp words not kept"
    for good in ["Shikotsu", "อยากไป Biei มาก", "อันนี้คือทะเลสาบที่สวยมากเลยครับ"]:
        assert degenerate(good, th) == good, f"false positive: {good!r}"
    assert degenerate("นะ นะ นะ นะ นะ", th) is None, "repeat-token rule regressed"
    assert degenerate("มมมมมม", th) is None, "repeated-char rule regressed"

    # no subtitles block at all: only the universal repeat rules apply
    bare = Rules()
    for good in ["Hú, csomára jön!", "людям то же самое", "บุคaiserอะไร", "We went to the lake"]:
        assert degenerate(good, bare) == good, f"default rules altered: {good!r}"
    assert degenerate("la la la la la", bare) is None, "repeat-token rule needs no config"

    # another series entirely: Japanese speech, Thai never occurs
    ja = Rules("kana", ["thai", "cyrillic"], ["Wi", "Fi"])
    assert degenerate("ここはすごいzzqxですね", ja) is None, "mixed-token rule should follow speech_script"
    assert degenerate("สวัสดี", ja) is None, "drop_scripts should follow the config"
    try: Rules("klingon"); raise AssertionError("unknown script accepted")
    except SystemExit: pass
    print("selftest: all assertions passed")

if A.selftest:
    run_selftest()
    raise SystemExit(0)

CFG = {}; BASE = Path(".")
if A.config:
    CFG = json.load(open(A.config, encoding="utf-8")); BASE = Path(A.config).resolve().parent
SUB = CFG.get("subtitles", {})

def setting(flag, key, default):
    return flag if flag is not None else SUB.get(key, default)

def path_of(flag, value):
    return Path(flag) if flag else (BASE / value if value else None)

A.cut_lists = path_of(A.cut_lists, CFG.get("cut_lists"))
A.transcripts = path_of(A.transcripts, CFG.get("transcripts"))
A.out = path_of(A.out, SUB.get("out"))
if not (A.cut_lists and A.transcripts and A.out):
    AP.error("cut lists, transcripts and out are each needed, from a flag or from --config")
A.lang = A.lang or CFG.get("lang") or "th"
A.max_cue = setting(A.max_cue, "max_cue", 6.0)
A.max_no_speech = setting(A.max_no_speech, "max_no_speech", 0.6)
A.max_chars = setting(A.max_chars, "max_chars", 70)

OUT = Path(A.out); OUT.mkdir(parents=True, exist_ok=True)
FIXES = ([(k, v) for k, v in SUB.get("fixes", {}).items() if not k.startswith("_")]
         + [tuple(f.split("=>", 1)) for f in A.fix if "=>" in f])
STAMPS = path_of(A.stamps, CFG.get("stamps"))
WHITELIST = Rules(SUB.get("speech_script", ""), SUB.get("drop_scripts", []), SUB.get("keep_words", []),
                  json.load(open(STAMPS, encoding="utf-8")) if STAMPS and STAMPS.exists() else None)

total = 0
for p in sorted(Path(A.cut_lists).glob("e??.json")):
    d = json.load(open(p, encoding="utf-8")); ep = d["episode"]
    t = 0.0; cues = []
    for beat in d["beats"]:
        for s in beat["shots"]:
            dur = s["out"] - s["in"]
            if s.get("audio") != "music-only" and s.get("subtitles", True):
                tr = json.load(open(Path(A.transcripts) / (Path(s["file"]).stem + ".json"), encoding="utf-8"))
                for seg in tr["segments"]:
                    if seg["no_speech_prob"] > A.max_no_speech: continue
                    cleaned = degenerate(seg["text"], WHITELIST)
                    if cleaned is None: continue
                    a, b = max(seg["start"], s["in"]), min(seg["end"], s["out"])
                    if b - a < 0.4: continue
                    text = cleaned.strip()
                    for pat, rep in FIXES: text = re.sub(pat, rep, text, flags=re.I)
                    words = [w for w in seg.get("words", []) if s["in"] <= w["s"] < s["out"]]
                    if b - a > A.max_cue and len(words) > 6:
                        # fix 2026-09-20: this chunk text is rebuilt from raw word tokens, which
                        # bypassed the hallucination strip and the fix list above -- rerun both,
                        # or the very tokens just stripped from `text` come back here.
                        n = int((b - a) // A.max_cue) + 1; chunk = max(1, len(words) // n)
                        for i in range(0, len(words), chunk):
                            ws = words[i:i+chunk]
                            ctext = degenerate("".join(w["w"] for w in ws).strip(), WHITELIST)
                            if ctext is None: continue
                            for pat, rep in FIXES: ctext = re.sub(pat, rep, ctext, flags=re.I)
                            cues.append((t + ws[0]["s"] - s["in"],
                                         t + min(ws[-1]["e"], s["out"]) - s["in"], ctext))
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
