#!/bin/bash
# Render an HTML slide to 1920x1080 PNG.
# Usage: ./render.sh input.html output.png
# Why window=1920x1161: headless Brave/Chrome reserves ~81px for chrome-UI
# even in --headless=new, so content viewport is only 999px tall at
# window=1920x1080. Rendering at 1161 gives full 1080 content area; we
# then crop bottom 81px to produce a clean 1920x1080 PNG.
set -e
INPUT="$1"
OUTPUT="$2"
TMP="${OUTPUT%.png}.raw.png"

"/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" \
  --headless=new --disable-gpu --hide-scrollbars \
  --window-size=1920,1161 --force-device-scale-factor=1 \
  --virtual-time-budget=4000 \
  --screenshot="$TMP" "file://$INPUT" 2>/dev/null

python3 -c "
from PIL import Image
img = Image.open('$TMP')
img.crop((0, 0, 1920, 1080)).save('$OUTPUT')
"
rm -f "$TMP"
echo "$OUTPUT"
