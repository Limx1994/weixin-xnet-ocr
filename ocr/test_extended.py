#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extended acceptance: input formats, large images, false-positive control.

Covers gaps the main suite does not:
  - JPEG / BMP / RGBA / palette / colour inputs
  - large images (performance and memory)
  - false positives: a no-text image must not yield confident text lines
  - repeated runs into the same output directory
"""
import sys
import os
import json
import time
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
WEIXIN_DIR = paths.weixin_dir() or ""

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.abspath(os.path.join(HERE, "_ext"))
FMT = os.path.abspath(os.path.join(WORK, "formats"))
FONT = r"C:\Windows\Fonts\msyh.ttc"


def run(path, out, timeout=1800):
    env = dict(os.environ)
    env["PATH"] = WEIXIN_DIR + os.pathsep + env.get("PATH", "")
    t0 = time.time()
    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "ocr.py"), path, "--long", "960", "--out", out],
        capture_output=True, text=True, env=env, errors="replace", timeout=timeout)
    return proc.returncode, proc.stdout + proc.stderr, time.time() - t0


def read_lines(out):
    p = os.path.join(out, "result.json")
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as fh:
        return json.load(fh)["lines"]


def make_base():
    img = Image.new("RGB", (820, 220), (255, 255, 255))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, 40)
    d.text((60, 50), "格式兼容性测试", font=f, fill=(25, 25, 25))
    d.text((60, 140), "Format Compatibility 2024", font=f, fill=(25, 25, 25))
    return img


def main():
    os.makedirs(FMT, exist_ok=True)
    base = make_base()
    results = []

    # --- format coverage ---
    variants = [
        ("png_rgb", base.convert("RGB"), "PNG"),
        ("jpg_rgb", base.convert("RGB"), "JPEG"),
        ("bmp_rgb", base.convert("RGB"), "BMP"),
        ("png_rgba", base.convert("RGBA"), "PNG"),
        ("png_gray", base.convert("L"), "PNG"),
        ("png_pal", base.convert("P"), "PNG"),
        ("tif_rgb", base.convert("RGB"), "TIFF"),
    ]
    for name, img, fmt in variants:
        path = os.path.join(FMT, name + ".img")
        try:
            img.save(path, format=fmt)
        except Exception as exc:
            results.append((name, False, "save failed: %s" % exc))
            continue
        code, log, dt = run(path, os.path.join(WORK, name))
        lines = read_lines(os.path.join(WORK, name))
        if code != 0 or lines is None:
            results.append((name, False, "exit %d" % code))
            continue
        texts = "".join(l["text"] for l in lines)
        ok = ("格式兼容性测试" in texts) or ("Format Compatibility 2024" in texts)
        results.append((name, ok, "%.1fs lines=%d %r" % (dt, len(lines), texts[:30])))

    # --- large image ---
    big = Image.new("RGB", (4000, 2600), (255, 255, 255))
    d = ImageDraw.Draw(big)
    f = ImageFont.truetype(FONT, 60)
    for i in range(6):
        d.text((120, 140 + i * 380), "大图测试第%d行 LargeImage" % (i + 1),
               font=f, fill=(20, 20, 20))
    big_path = os.path.join(FMT, "large.png")
    big.save(big_path)
    code, log, dt = run(big_path, os.path.join(WORK, "large"))
    lines = read_lines(os.path.join(WORK, "large"))
    if not lines:
        results.append(("large_4000x2600", False, "no result"))
    else:
        joined = "".join(l["text"] for l in lines)
        # Downscaling a 4000px image to the 960 long side shrinks glyphs, so a
        # few Latin letters may degrade; require the six lines and the Chinese
        # bodies, which is what the pipeline can guarantee at this scale.
        ok = (len(lines) >= 6
              and all(("大图测试第%d" % (i + 1)) in lines[i]["text"] for i in range(6)))
        results.append(("large_4000x2600", ok,
                        "%.1fs lines=%d sample=%r" % (dt, len(lines), lines[0]["text"])))

    # --- false positives: no-text image must not produce text ---
    blank = Image.new("RGB", (700, 400), (245, 246, 248))
    d = ImageDraw.Draw(blank)
    d.ellipse((150, 100, 550, 300), fill=(190, 205, 220))
    d.rectangle((100, 320, 600, 350), fill=(160, 175, 195))
    bp = os.path.join(FMT, "notext.png")
    blank.save(bp)
    code, log, dt = run(bp, os.path.join(WORK, "notext"))
    # The child process may run from a different cwd, so resolve to absolute.
    lines = read_lines(os.path.abspath(os.path.join(WORK, "notext")))
    # Distinguish "no result file" (None) from "recognised nothing" ([]):
    # an empty list is the expected outcome for a text-free image.
    junk = ([] if lines is None
            else [l["text"] for l in lines if l["text"].strip()])
    if lines is None:
        junk = ["<no result>"]
    ok = len(junk) == 0
    results.append(("no_text_false_positive", ok, "lines=%r" % junk))

    # --- repeated run into the same directory ---
    path = os.path.join(FMT, "png_rgb.img")
    ok = True
    notes = []
    for k in range(2):
        code, log, dt = run(path, os.path.join(WORK, "repeat"))
        lines = read_lines(os.path.join(WORK, "repeat"))
        texts = "".join(l["text"] for l in lines) if lines else ""
        good = code == 0 and "格式兼容性测试" in texts
        ok = ok and good
        notes.append("run%d:%s" % (k + 1, "ok" if good else "bad"))
    results.append(("repeat_same_outdir", ok, " ".join(notes)))

    passed = 0
    for name, ok, note in results:
        print("%-24s %s  %s" % (name, "PASS" if ok else "FAIL", note))
        if ok:
            passed += 1
    print("--- %d/%d passed ---" % (passed, len(results)))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
