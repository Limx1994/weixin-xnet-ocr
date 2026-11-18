#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a realistic multi-line test image for end-to-end OCR."""
import sys
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "test_scene.png")
    lines = [
        "微信图片文字提取",
        "基于自研OCR技术",
        "Detection and Recognition",
        "2024年识别准确率测试",
    ]
    width, line_h, pad = 720, 72, 60
    height = pad * 2 + line_h * len(lines)
    img = Image.new("RGB", (width, height), (255, 255, 255))
    drawer = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 40)
    y = pad
    for ln in lines:
        box = drawer.textbbox((0, 0), ln, font=font)
        tw = box[2] - box[0]
        x = (width - tw) // 2
        drawer.text((x, y), ln, font=font, fill=(20, 20, 20))
        y += line_h
    img.save(out)
    print("saved %s (%dx%d) lines=%d" % (out, width, height, len(lines)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
