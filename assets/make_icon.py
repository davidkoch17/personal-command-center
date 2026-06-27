"""Generate the Command Center launcher icon (assets/icon.ico) — crosshair brand.

The v3 brand mark is a **crosshair / target** (precision, focus, the "command
center" framing). Run once to (re)create the Desktop-shortcut icon:

    python assets/make_icon.py

Colors mirror the Cockpit palette: accent-soft #1E3A8A (background disc), accent
#2563EB (ring), and a bright #60A5FA for the crosshair arms + center dot.
"""
from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parent
OUT = ASSETS / "icon.ico"

NAVY = (30, 58, 138, 255)    # accent-soft #1E3A8A — background disc
RING = (37, 99, 235, 255)    # accent      #2563EB — outer ring
BRIGHT = (96, 165, 250, 255)  # accent bright #60A5FA — crosshair + dot

img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Navy background disc.
draw.ellipse([16, 16, 240, 240], fill=NAVY)

# Outer ring.
draw.ellipse([44, 44, 212, 212], outline=RING, width=8)

# Crosshair arms — four bright bars crossing the ring toward the centre, with a
# gap at the middle so the centre dot reads clearly (classic reticle).
draw.rectangle([122, 24, 134, 100], fill=BRIGHT)    # top
draw.rectangle([122, 156, 134, 232], fill=BRIGHT)   # bottom
draw.rectangle([24, 122, 100, 134], fill=BRIGHT)    # left
draw.rectangle([156, 122, 232, 134], fill=BRIGHT)   # right

# Centre dot (target point).
draw.ellipse([114, 114, 142, 142], fill=BRIGHT)

# Save as ICO (multiple sizes embedded for crisp rendering at every scale).
img.save(OUT, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(f"wrote {OUT}")
