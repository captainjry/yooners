#!/bin/sh
# Step 11: two-pass linear loudnorm on the audio only; the video stream is copied.
# Needed because the pipeline has no normalization stage: each episode's level is whatever its
# per-shot volume automation produced, and unnormalized finals measured -17.7 to -25 LUFS.
#
#   sh normalize_loudness.sh <file>.mp4 [--target -20] [--tp -1.5] [--lra 14] [--qc <dir>]
#
# The original is moved to <qc>/<name>.pre-loudnorm.mp4 and kept.
# Normalize BEFORE upload: re-normalizing a published video means re-uploading it, which loses
# its URL, views and comments.
set -e
F="$1"; shift || true
[ -s "$F" ] || { echo "usage: sh normalize_loudness.sh <file.mp4> [--target -20] [--tp -1.5] [--lra 14]"; exit 1; }
I=-20; TP=-1.5; LRA=14; QC="$(dirname "$F")/qc"
while [ $# -gt 0 ]; do
  case "$1" in
    --target) I="$2"; shift 2 ;;
    --tp) TP="$2"; shift 2 ;;
    --lra) LRA="$2"; shift 2 ;;
    --qc) QC="$2"; shift 2 ;;
    *) shift ;;
  esac
done
mkdir -p "$QC"
B=$(basename "$F" .mp4)
KEEP="$QC/$B.pre-loudnorm.mp4"
JSON="$QC/$B-loudnorm-pass1.json"
[ -e "$KEEP" ] && { echo "ABORT: $KEEP already exists - this file looks normalized already"; exit 1; }

echo "--- pass 1: measure"
ffmpeg -hide_banner -nostdin -i "$F" \
  -af "loudnorm=I=$I:TP=$TP:LRA=$LRA:print_format=json" -vn -f null - 2>&1 \
  | sed -n '/^{/,/^}/p' > "$JSON"
cat "$JSON"

get() { grep "\"$1\"" "$JSON" | sed 's/.*: *"\([^"]*\)".*/\1/'; }
MI=$(get input_i); MTP=$(get input_tp); MLRA=$(get input_lra)
MTH=$(get input_thresh); MOFF=$(get target_offset)
[ -n "$MI" ] || { echo "ABORT: pass 1 produced no measurement"; exit 1; }

echo "--- pass 2: apply linear (video copied)"
TMP="$(dirname "$F")/.norm-$B.mp4"
ffmpeg -hide_banner -nostdin -y -i "$F" -map 0:v -map 0:a -c:v copy \
  -af "loudnorm=I=$I:TP=$TP:LRA=$LRA:measured_I=$MI:measured_TP=$MTP:measured_LRA=$MLRA:measured_thresh=$MTH:offset=$MOFF:linear=true:print_format=summary" \
  -c:a aac -b:a 192k -ar 48000 -movflags +faststart "$TMP"

mv "$F" "$KEEP"
mv "$TMP" "$F"
echo "--- verify"
ffmpeg -hide_banner -nostdin -i "$F" -af ebur128=peak=true -vn -f null - 2>&1 | grep -E '^\s+(I|Peak):' | tail -2
echo "normalized $MI -> $I LUFS; original kept at $KEEP"
