#!/bin/sh
# Step 10: render every missing episode, one at a time, with all known fixes.
# Idempotent: it skips episodes whose final already exists, so a relaunch resumes. Leave the
# finished finals in place while it runs, or it re-renders them.
#
#   PROJECT=... PROXY=... FINAL=... LOGS=... ORDER="01 02 03" sh render_batch.sh
#   nohup sh render_batch.sh > "$LOGS/render-batch.log" 2>&1 &     # then tail that log
#
# Before relaunching after a failure, check the process list: a killed wrapper can leave a
# sibling sh alive, and two copies race for the same output file.

# ---------------- config ----------------
PROJECT="${PROJECT:?set PROJECT to the HyperFrames project directory}"
PROXY="${PROXY:?set PROXY to the 1 s-keyframe proxy directory}"
FINAL="${FINAL:?set FINAL to the output directory}"
LOGS="${LOGS:-$FINAL/logs}"
ORDER="${ORDER:-01 02 03 04 05 06 07 08 09 10}"
NAME="${NAME:-Episode}"                    # output files are $NAME-ENN.mp4
COMP="${COMP:-compositions/episodes/e%s.html}"   # %s is the episode number
RESOLUTION="${RESOLUTION:-landscape-4k}"
CRF="${CRF:-18}"
GAP="${GAP:-90}"                           # seconds between renders
MIN_FREE_MB="${MIN_FREE_MB:-8000}"
PROBE_CLIP="${PROBE_CLIP:-}"               # a proxy to check for 1 s keyframes; empty = first found
# Absolute path to the CLI. Use this rather than `npx hyperframes@latest`, which reinstalls a
# clean copy and drops any local patch to the installed CLI.
HF="${HF:-npx hyperframes}"
# ----------------------------------------

cd "$PROJECT" || exit 1
mkdir -p "$LOGS" "$FINAL"

export PRODUCER_STREAMING_ENCODE_MAX_DURATION_SECONDS=3600
export PRODUCER_PLAYER_READY_TIMEOUT_MS=300000
export PRODUCER_RENDER_READY_TIMEOUT_MS=300000
export PRODUCER_PUPPETEER_PROTOCOL_TIMEOUT_MS=1800000

# 1. proxy pre-flight: a keyframe every second (see reference/build.md)
[ -n "$PROBE_CLIP" ] || PROBE_CLIP=$(ls "$PROXY"/*.mp4 2>/dev/null | head -1)
[ -n "$PROBE_CLIP" ] || { echo "ABORT: no proxies in $PROXY"; exit 1; }
k=$(ffprobe -v error -select_streams v:0 -show_entries frame=key_frame -of csv=p=0 \
     -read_intervals "%+#60" "$PROBE_CLIP" | grep -c 1)
echo "PROXY $PROXY  keyframes in first 60 frames: $k (expect >= 2)"
[ "$k" -ge 2 ] || { echo "ABORT: sparse keyframes; re-cut the proxies with -g fps"; exit 1; }

# 2. render every missing episode, one at a time, with a clean slate before each
for ep in $ORDER; do
  out="$FINAL/$NAME-E$ep.mp4"
  [ -s "$out" ] && { echo "SKIP e$ep (exists)"; continue; }
  comp=$(printf "$COMP" "$ep")
  [ -f "$comp" ] || { echo "SKIP e$ep (no composition at $comp)"; continue; }
  free=$(df -m "$FINAL" | awk 'NR==2{print $4}')
  [ "$free" -lt "$MIN_FREE_MB" ] && { echo "ABORT e$ep low disk ${free}MB"; exit 1; }
  # a gap plus a browser kill: back-to-back starts produced transient
  # VIDEO_SOURCE_UNRENDERABLE / readiness-timeout failures on clean proxies
  sleep "$GAP"
  taskkill //F //IM chrome-headless-shell.exe >/dev/null 2>&1 || \
    pkill -f chrome-headless-shell >/dev/null 2>&1
  # stale transaction dirs only: anything here now belongs to a dead run, since no render is alive
  rm -rf "$FINAL"/."$NAME-E$ep".hf-transaction-*
  echo "START e$ep $(date +%H:%M:%S)"
  $HF render -c "$comp" -q high --crf "$CRF" --gpu --workers 1 \
      --resolution "$RESOLUTION" --player-ready-timeout 300000 \
      -o "$out" > "$LOGS/render-e$ep.log" 2>&1
  if [ -s "$out" ]; then
    echo "DONE e$ep $(du -m "$out" | cut -f1)MB $(date +%H:%M:%S)"
  else
    echo "FAILED e$ep"
    grep -E 'Failure summary' "$LOGS/render-e$ep.log" \
      | grep -oE '"failedStage":"[^"]*","error":"[^"]{0,300}'
  fi
done
echo "ALL DONE $(date +%H:%M:%S)"; ls -la "$FINAL"/*.mp4
