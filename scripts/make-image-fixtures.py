"""Generate varied small images for the 100+ image acceptance check."""
import sys
from pathlib import Path
from PIL import Image

root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=True)
for index in range(105):
    Image.new("RGB", (64, 48), (index * 2, 60, 130)).save(root / f"frame-{index:03}.png")
