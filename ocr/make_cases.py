#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a battery of test images covering realistic OCR scenarios."""
import sys
import os
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = {
    "msyh": r"C:\Windows\Fonts\msyh.ttc",
    "simhei": r"C:\Windows\Fonts\simhei.ttf",
    "simsun": r"C:\Windows\Fonts\simsunb.ttf",
    "deng": r"C:\Windows\Fonts\Deng.ttf",
    "kaiti": r"C:\Windows\Fonts\STKAITI.TTF",
}
OUT = os.path.join(HERE, "test_images")


def _font(name, size):
    path = FONTS.get(name, FONTS["msyh"])
    return ImageFont.truetype(path, size)


def case_plain():
    img = Image.new("RGB", (760, 300), (255, 255, 255))
    d = ImageDraw.Draw(img)
    f = _font("msyh", 40)
    d.text((60, 50), "微信扫码支付成功", font=f, fill=(30, 30, 30))
    d.text((60, 130), "订单金额 128.50 元", font=f, fill=(30, 30, 30))
    d.text((60, 210), "Order No.20240118", font=f, fill=(30, 30, 30))
    return img, ["微信扫码支付成功", "订单金额 128.50 元", "Order No.20240118"]


def case_mixed_fonts():
    img = Image.new("RGB", (820, 280), (250, 250, 250))
    d = ImageDraw.Draw(img)
    # Full-width punctuation absent from charset_zh13562 is rendered with its
    # half-width equivalent, which is what the model can emit.
    d.text((40, 40), "黑体标题:文本检测结果", font=_font("simhei", 36), fill=(0, 0, 0))
    d.text((40, 120), "微软雅黑正文识别率接近百分之百", font=_font("msyh", 32), fill=(20, 20, 20))
    d.text((40, 200), "楷体注释 Kaiti Note 0123", font=_font("kaiti", 32), fill=(40, 40, 40))
    return img, ["黑体标题:文本检测结果", "微软雅黑正文识别率接近百分之百", "楷体注释 Kaiti Note 0123"]


def case_small_text():
    img = Image.new("RGB", (900, 220), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for i, t in enumerate(["小字号第一行 12px", "第二行 ABCDEFG", "第三行 混合 mixed 文字"]):
        d.text((40, 20 + i * 65), t, font=_font("msyh", 20), fill=(50, 50, 50))
    return img, ["小字号第一行 12px", "第二行 ABCDEFG", "第三行 混合 mixed 文字"]


def case_dense_lines():
    img = Image.new("RGB", (700, 400), (255, 255, 255))
    d = ImageDraw.Draw(img)
    lines = ["第一行:微信OCR端到端测试", "第二行:检测与识别串联",
             "第三行:CTC解码输出文本", "第四行:XNet推理引擎"]
    for i, t in enumerate(lines):
        d.text((40, 30 + i * 90), t, font=_font("msyh", 30), fill=(25, 25, 25))
    return img, lines


def case_noisy_bg():
    img = Image.new("RGB", (800, 260), (235, 235, 230))
    d = ImageDraw.Draw(img)
    rng = random.Random(7)
    for _ in range(900):
        x, y = rng.randrange(800), rng.randrange(260)
        v = rng.randrange(200, 250)
        d.point((x, y), fill=(v, v, v - 5))
    d.text((50, 60), "噪声背景上的文字识别", font=_font("msyh", 40), fill=(15, 15, 15))
    d.text((50, 150), "Noise Background Test 2024", font=_font("msyh", 34), fill=(20, 20, 20))
    return img, ["噪声背景上的文字识别", "Noise Background Test 2024"]


def case_low_contrast():
    img = Image.new("RGB", (760, 220), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((50, 50), "低对比度文字 Low Contrast", font=_font("msyh", 40), fill=(170, 170, 170))
    d.text((50, 140), "灰度接近背景 Gray Text", font=_font("msyh", 36), fill=(190, 190, 190))
    return img, ["低对比度文字 Low Contrast", "灰度接近背景 Gray Text"]


def case_blur():
    img = Image.new("RGB", (780, 240), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((50, 60), "轻微模糊的文字样本", font=_font("msyh", 40), fill=(25, 25, 25))
    d.text((50, 150), "Blurred Text Sample 01", font=_font("msyh", 36), fill=(25, 25, 25))
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    return img, ["轻微模糊的文字样本", "Blurred Text Sample 01"]


def case_no_text():
    img = Image.new("RGB", (500, 300), (240, 242, 245))
    d = ImageDraw.Draw(img)
    d.ellipse((120, 80, 380, 220), fill=(180, 200, 220))
    d.rectangle((60, 240, 440, 260), fill=(150, 170, 190))
    return img, []


def case_single_char():
    img = Image.new("RGB", (400, 200), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((140, 60), "微", font=_font("msyh", 60), fill=(0, 0, 0))
    return img, ["微"]


def case_long_line():
    text = "这是一行比较长的中文文本用于验证检测模型在长文本场景下不会把文字截断成多个片段"
    # Size the canvas from the rendered text so the line is never clipped.
    probe = Image.new("L", (8, 8), 255)
    drawer = ImageDraw.Draw(probe)
    font = _font("msyh", 30)
    box = drawer.textbbox((0, 0), text, font=font)
    width = box[2] - box[0] + 80
    img = Image.new("RGB", (width, 160), (255, 255, 255))
    drawer = ImageDraw.Draw(img)
    drawer.text((40, 50), text, font=font, fill=(20, 20, 20))
    return img, [text]


CASES = {
    "plain": case_plain,
    "mixed_fonts": case_mixed_fonts,
    "small_text": case_small_text,
    "dense_lines": case_dense_lines,
    "noisy_bg": case_noisy_bg,
    "low_contrast": case_low_contrast,
    "blur": case_blur,
    "no_text": case_no_text,
    "single_char": case_single_char,
    "long_line": case_long_line,
}


def main():
    os.makedirs(OUT, exist_ok=True)
    manifest = {}
    for name, fn in CASES.items():
        img, expected = fn()
        path = os.path.join(OUT, name + ".png")
        img.save(path)
        manifest[name] = {"path": path, "expected": expected}
        print("%-14s %s expected=%d" % (name, img.size, len(expected)))
    import json
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print("manifest written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
