import python_avatars as pa
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM
import io
from PIL import Image

# Generate Avatar
avatar = pa.Avatar.random()
svg = avatar.render()

# Write to temp file because svglib reads from file or path
with open("temp_avatar.svg", "w", encoding="utf-8") as f:
    f.write(svg)

# Render to PNG
drawing = svg2rlg("temp_avatar.svg")
out = io.BytesIO()
renderPM.drawToFile(drawing, out, fmt="PNG")

# Load with PIL
img = Image.open(io.BytesIO(out.getvalue())).convert("RGBA")
print(f"Generated successfully: {img.size}")
