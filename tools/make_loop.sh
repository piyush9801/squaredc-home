#!/usr/bin/env bash
# Fold the rendered continuation (frames 121..240) into a seamless 96-frame loop: the last 24 rendered frames are
# blended into the first 24, so frame 96 runs straight back into frame 1.
set -euo pipefail
RAW="${1:-qa/s01loop_raw}"; OUT="${2:-public/frames/s01loop}"; L=96; C=24; START=121
mkdir -p "$OUT"
for ((i=0; i<L; i++)); do
  a=$(printf "%s/f_%04d.webp" "$RAW" $((START + i)))
  o=$(printf "%s/l_%04d.webp" "$OUT" $((i + 1)))
  if (( i < C )); then
    e=$(printf "%s/f_%04d.webp" "$RAW" $((START + L + i)))
    pct=$(( 100 * i / C ))
    magick "$e" "$a" -compose blend -define compose:args=$pct -composite -quality 80 "$o"
  else
    cp "$a" "$o"
  fi
done
ls "$OUT" | wc -l
