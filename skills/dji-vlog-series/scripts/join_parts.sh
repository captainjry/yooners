#!/bin/sh
# Step 10: losslessly join one episode's rendered parts back into the whole episode, then check
# the seams.
#
#   FINAL=<media>/final NAME=Series sh join_parts.sh 04 3 --total 10982 --seams 3868,6924
#   FINAL=<media>/final NAME=Series sh join_parts.sh 06 2 --total 10144 --seams 4834
#
# --total and --seams come from build_episodes.py --parts, which prints both.
#
# Parts are cut only at beat boundaries and each part's offset is snapped up to the joined frame
# grid, so every seam is frame-exact: sum(part frames) == whole frames, no duplicated or dropped
# frame, and the bed's data-media-start equals the seam time exactly, so the music is
# sample-continuous across the cut. -c copy means no re-encode: bit-identical video.
set -e
EP="$1"; NP="$2"; shift 2 || true
TOTAL=""; SEAMS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --total) TOTAL="$2"; shift 2 ;;
    --seams) SEAMS=$(echo "$2" | tr ',' ' '); shift 2 ;;
    *) shift ;;
  esac
done
[ -n "$EP" ] && [ -n "$NP" ] || {
  echo "usage: sh join_parts.sh <episode NN> <part count> [--total <frames>] [--seams f1,f2]"; exit 1; }

FINAL="${FINAL:?set FINAL to the directory holding the part MP4s}"
NAME="${NAME:-Episode}"
FPS="${FPS:-25}"
OUT="$FINAL/$NAME-E$EP.mp4"
LIST="$FINAL/.concat-E$EP.txt"
[ -e "$OUT" ] && { echo "ABORT: $OUT already exists"; exit 1; }

# 1. concat list, refusing to start unless every part is present and non-empty
: > "$LIST"
i=1
while [ "$i" -le "$NP" ]; do
  P="$FINAL/$NAME-E$EP-part$i.mp4"
  [ -s "$P" ] || { echo "ABORT: missing $P"; exit 1; }
  echo "file '$P'" >> "$LIST"
  printf 'part%s  %s frames  %ss\n' "$i" \
    "$(ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of csv=p=0 "$P")" \
    "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$P")"
  i=$((i + 1))
done

# 2. lossless concat
echo "--- concat -> $OUT"
ffmpeg -hide_banner -nostdin -f concat -safe 0 -i "$LIST" -c copy -movflags +faststart "$OUT" \
  2> "$FINAL/.concat-E$EP.log"
tail -3 "$FINAL/.concat-E$EP.log"

# 3. duration + video packet count (must equal the whole-episode frame count)
echo "--- duration / streams"
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate -of csv=p=0 "$OUT"
N=$(ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of csv=p=0 "$OUT")
echo "video packets: $N  (expected ${TOTAL:-?})"
[ -n "$TOTAL" ] && { [ "$N" = "$TOTAL" ] && echo "FRAME COUNT OK" || echo "FRAME COUNT MISMATCH"; }

# 4. non-monotonous DTS: the classic symptom of a bad concat
echo "--- DTS check (expect no lines)"
grep -c "Non-monotonous DTS" "$FINAL/.concat-E$EP.log" || true
ffmpeg -hide_banner -nostdin -v warning -i "$OUT" -c copy -f null - 2>&1 \
  | grep -E "Non-monotonous DTS|non-monotonic|DTS .* PTS" || echo "no DTS warnings"

# 5. silence around each seam: a bed discontinuity or a dropped audio frame shows here
echo "--- silencedetect near the seams"
for f in $SEAMS; do
  ss=$(awk -v f="$f" -v r="$FPS" 'BEGIN{printf "%.3f", (f/r)-3}')
  echo "seam frame $f @ $(awk -v f="$f" -v r="$FPS" 'BEGIN{printf "%.2f", f/r}')s (window ${ss}s +6s)"
  ffmpeg -hide_banner -nostdin -v info -ss "$ss" -t 6 -i "$OUT" \
    -af silencedetect=n=-50dB:d=0.05 -vn -f null - 2>&1 \
    | grep -E "silence_(start|end|duration)" || echo "  no silence in window"
done

echo "--- done: $OUT ($(du -m "$OUT" | cut -f1) MB)"
echo "NEXT: sh qc_episode.sh \"$OUT\""
