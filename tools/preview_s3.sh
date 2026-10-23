#!/bin/sh
# Scene 03 preview video, as the page shows it: every frame composed with the headline, the in-front matte and the
# notes (tools/compose_s3.py), then a short hold on each rest (the moment, alongside, looking back).
# tools/preview_s3.sh qa/s03_raw qa/s03_fore qa/s03_preview.mp4
set -e
frames=${1:-qa/s03_raw}; mattes=${2:-qa/s03_fore}; out=${3:-qa/s03_preview.mp4}
comp=qa/s03_comp; seq=$(mktemp -d)
python3 tools/compose_s3.py "$frames" "$mattes" "$frames/track.json" "$comp" 261 565 > /dev/null
n=0
add() { n=$((n + 1)); ln -s "$PWD/$comp/c_$(printf %04d $1).png" "$seq/s_$(printf %05d $n).png"; }
for f in $(seq 261 565); do
  add $f
  case $f in
    261) for i in $(seq 12); do add $f; done ;;
    325) for i in $(seq 40); do add $f; done ;;
    425) for i in $(seq 26); do add $f; done ;;
    565) for i in $(seq 36); do add $f; done ;;
  esac
done
ffmpeg -y -loglevel error -framerate 24 -i "$seq/s_%05d.png" -c:v libx264 -preset slow -crf 19 -pix_fmt yuv420p -movflags +faststart "$out"
rm -rf "$seq"
echo "$out: $n frames"
