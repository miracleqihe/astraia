"""Rebuild the fixed indexed-color social-card artwork using bundled fonts."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT, SCALE = 1200, 630, 2
image = Image.new('RGB', (WIDTH * SCALE, HEIGHT * SCALE), '#080d18')
draw = ImageDraw.Draw(image)

def p(value):
    return int(value * SCALE)

draw.rectangle((p(45), p(35), p(1155), p(595)), outline='#405065', width=p(1))
draw.line((p(95), p(430), p(495), p(430)), fill='#405065', width=p(1))
draw.ellipse((p(656), p(76), p(1134), p(554)), outline='#765f3d', width=p(1))
draw.ellipse((p(656), p(225), p(1134), p(405)), outline='#33414d', width=p(1))
draw.ellipse((p(790), p(76), p(1000), p(554)), outline='#33414d', width=p(1))
title_font = ImageFont.truetype(str(ROOT / 'public/fonts/cinzel-600.ttf'), p(68))
label_font = ImageFont.truetype(str(ROOT / 'public/fonts/cinzel-400.ttf'), p(22))
draw.text((p(92), p(165)), 'ASTRAIA', font=title_font, fill='#efece6')
draw.text((p(96), p(267)), 'FOLKLORE ATLAS', font=label_font, fill='#c29d59')
image = image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS).quantize(colors=128, dither=Image.Dither.NONE)
palette = bytes(image.getpalette()).ljust(768, b'\0')
pixels = image.tobytes()
rows = b''.join(b'\0' + pixels[y * WIDTH:(y + 1) * WIDTH] for y in range(HEIGHT))
(ROOT / 'scripts/share-template.bin').write_bytes(palette + rows)
print('Generated share template with bundled Cinzel fonts.')
