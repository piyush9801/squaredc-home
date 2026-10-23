#!/bin/sh
# Scene 03 mattes: Blender writes them grey (what stands in front of the headline, sRGB-encoded); the page wants white
# with that as alpha, linear. Lossy alpha at q70 is ~9 KB a frame and within 0.3% of the source.
# tools/make_mattes.sh qa/s03_fore public/frames/s03m
set -e
src=${1:-qa/s03_fore}; dst=${2:-public/frames/s03m}
mkdir -p "$dst"; tmp=$(mktemp -d)
for f in "$src"/m_*.png; do
  b=$(basename "$f" .png)
  magick "$f" -set colorspace sRGB -colorspace RGB -set colorspace Gray \( +clone -fill white -colorize 100 \) +swap -alpha off \
    -compose CopyOpacity -composite PNG32:"$tmp/$b.png"
  cwebp -quiet -q 80 -alpha_q 70 -alpha_filter best -exact "$tmp/$b.png" -o "$dst/$b.webp"
done
rm -rf "$tmp"
ls "$dst" | wc -l
