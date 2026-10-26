#!/bin/zsh
# compare_sheet.sh OUT.jpg "label1:dir1/prefix1" "label2:dir2/prefix2" ... -- frame frame ...
# One row per frame, one column per version, each cell labelled. Missing cells are left dark.
set -e
out=$1; shift
cols=(); while [[ $1 != -- ]]; do cols+=$1; shift; done; shift
frames=($@)
tmp=$(mktemp -d)
r=0
for f in $frames; do
  cells=()
  c=0
  for spec in $cols; do
    lab=${spec%%:*}; pre=${spec#*:}
    src=$(printf "%s%04d.webp" $pre $f)
    cell=$tmp/c_${r}_${c}.png
    if [[ -f $src ]]; then magick $src -resize 640x360! $tmp/img.png; else magick -size 640x360 xc:'#0b0714' $tmp/img.png; fi
    magick -size 640x30 xc:'#120c1f' -fill '#e9e2ff' -font /System/Library/Fonts/SFNS.ttf -pointsize 15 -gravity west -annotate +12+0 "$lab  ·  frame $f" $tmp/lab.png
    magick $tmp/lab.png $tmp/img.png -append $cell
    cells+=$cell; c=$((c+1))
  done
  magick $cells +append $tmp/row_$r.png
  r=$((r+1))
done
magick $tmp/row_*(n) -append -quality 86 $out
rm -rf $tmp
echo "wrote $out"
