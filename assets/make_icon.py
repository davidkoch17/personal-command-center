"""Generate the navy Cockpit launcher icon (assets/icon.ico).

Run once to (re)create the Desktop-shortcut icon:

    python assets/make_icon.py

Colors mirror the Cockpit palette: accent-soft #1E3A8A (background), accent
#2563EB (ring), and a bright #60A5FA center dot.
"""
from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parent
OUT = ASSETS / "icon.ico"

img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Navy background circle
draw.ellipse([20, 20, 236, 236], fill=(30, 58, 138, 255))  # accent-soft #1E3A8A

# Inner ring (lighter navy)
draw.ellipse([50, 50, 206, 206], outline=(37, 99, 235, 255), width=6)  # accent #2563EB

# Center dot
draw.ellipse([110, 110, 146, 146], fill=(96, 165, 250, 255))  # accent bright #60A5FA

# Save as ICO (multiple sizes embedded)
img.save(OUT, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(f"wrote {OUT}")
