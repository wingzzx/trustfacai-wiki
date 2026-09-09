# -*- coding: utf-8 -*-
"""生成肥姐问财 favicon.ico：蓝底金"肥"，16/32/48 多尺寸"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "src", "static", "favicon.ico")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

S = 256
BLUE = (30, 58, 138)     # tailwind blue-900
AMBER = (251, 191, 36)   # tailwind amber-400

img = Image.new("RGB", (S, S), BLUE)
d = ImageDraw.Draw(img)
# 底部稍深的一条弧形装饰，增加质感
d.ellipse([-S*0.4, S*0.72, S*1.4, S*1.5], fill=(23, 45, 110))

font = None
for fp in [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"]:
    if os.path.exists(fp):
        font = ImageFont.truetype(fp, 148)
        print("font:", fp)
        break
assert font, "未找到中文字体"

bbox = d.textbbox((0, 0), "肥", font=font)
w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
d.text(((S - w) / 2 - bbox[0], (S - h) / 2 - bbox[1] - 6), "肥", font=font, fill=AMBER)

img.save(OUT, sizes=[(16, 16), (32, 32), (48, 48)])
print("saved:", OUT, os.path.getsize(OUT), "bytes")
