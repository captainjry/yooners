"""Step 3: local word-level transcription of every source clip.

Read-only on the originals; audio goes to a temp mono 16 kHz WAV per clip and is discarded.
Resumable: a clip whose JSON already exists is skipped.

  python transcribe_all.py --source <source> --out <review>/transcripts
  python transcribe_all.py --source <source> --out <review>/transcripts \
      --frame-index <review>/frame-index.json --model large-v3 --device cuda --first DJI_<last day>

Requires: pip install faster-whisper ; an ffmpeg on PATH (or --ffmpeg).
Output: <out>/<stem>.json per clip and <out>/_index.json (file -> summary), rewritten each clip.
"""
import argparse, json, subprocess, tempfile, time
from pathlib import Path

AP = argparse.ArgumentParser()
AP.add_argument("--source", required=True)
AP.add_argument("--out", required=True)
AP.add_argument("--frame-index", default="", help="frame-index.json; else every --ext file is used")
AP.add_argument("--ext", default=".MP4")
AP.add_argument("--prefix", default="")
AP.add_argument("--model", default="large-v3")
AP.add_argument("--device", default="cuda")
AP.add_argument("--compute-type", default="float16")
AP.add_argument("--language", default="", help="force a language; empty = detect per clip")
AP.add_argument("--first", default="", help="filename prefix to transcribe first (e.g. the last day)")
AP.add_argument("--ffmpeg", default="ffmpeg")
A = AP.parse_args()

SRC, OUT = Path(A.source), Path(A.out)
OUT.mkdir(parents=True, exist_ok=True)

if A.frame_index:
    files = [e["file"] for e in json.load(open(A.frame_index, encoding="utf-8"))]
else:
    files = sorted(p.name for p in SRC.iterdir() if p.suffix.lower() == A.ext.lower())
files = [f for f in files if f.startswith(A.prefix)]
# clips that answer an open question (usually the last day) go first
if A.first:
    files.sort(key=lambda f: (not f.startswith(A.first), f))

from faster_whisper import WhisperModel
model = WhisperModel(A.model, device=A.device, compute_type=A.compute_type)

index = {}
t0 = time.time()
for i, f in enumerate(files, 1):
    dst = OUT / (Path(f).stem + ".json")
    if dst.exists():
        index[f] = json.load(open(dst, encoding="utf-8"))["summary"]
        continue
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        subprocess.run([A.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(SRC / f),
                        "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)
        segs, info = model.transcribe(
            str(wav), vad_filter=True, word_timestamps=True, beam_size=5,
            # a vlog is not one continuous narrative: conditioning carries hallucinated text
            # from one unrelated clip into the next
            condition_on_previous_text=False,
            **({"language": A.language} if A.language else {}))
        out = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
                "no_speech_prob": round(s.no_speech_prob, 3),
                "words": [{"w": w.word, "s": round(w.start, 2), "e": round(w.end, 2)}
                          for w in (s.words or [])]} for s in segs]
    speech = sum(s["end"] - s["start"] for s in out)
    summary = {"language": info.language, "language_prob": round(info.language_probability, 2),
               "duration": round(info.duration, 2), "speech_seconds": round(speech, 1),
               "segments": len(out), "preview": " ".join(s["text"] for s in out)[:160]}
    json.dump({"file": f, "summary": summary, "segments": out}, open(dst, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    index[f] = summary
    json.dump(index, open(OUT / "_index.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[{i}/{len(files)}] {f} {info.language} speech={speech:.0f}s/{info.duration:.0f}s "
          f"elapsed={time.time()-t0:.0f}s", flush=True)
print("DONE", len(index))
