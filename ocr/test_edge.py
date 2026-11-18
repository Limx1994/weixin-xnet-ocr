#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Robustness checks: malformed and edge-case inputs must not crash."""
import sys
import os
import json
import subprocess
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
WEIXIN_DIR = paths.weixin_dir() or ""

HERE = os.path.dirname(os.path.abspath(__file__))
EDGE = os.path.join(HERE, "test_images", "edge")
OCR = os.path.join(HERE, "ocr_image.py")


def run(path, out):
    env = dict(os.environ)
    env["PATH"] = WEIXIN_DIR + os.pathsep + env.get("PATH", "")
    proc = subprocess.run([sys.executable, OCR, path, "--long", "960", "--out", out],
                          capture_output=True, text=True, env=env,
                          errors="replace", timeout=900)
    return proc.returncode, proc.stdout + proc.stderr


def main():
    os.makedirs(EDGE, exist_ok=True)
    cases = {}

    # 1x1 pixel
    p = os.path.join(EDGE, "px1.png")
    Image.new("RGB", (1, 1), (0, 0, 0)).save(p)
    cases["1x1 pixel"] = p

    # very wide thin strip
    p = os.path.join(EDGE, "thin_wide.png")
    Image.new("RGB", (3000, 12), (255, 255, 255)).save(p)
    cases["wide thin blank"] = p

    # solid black
    p = os.path.join(EDGE, "black.png")
    Image.new("RGB", (400, 200), (0, 0, 0)).save(p)
    cases["solid black"] = p

    # blank white
    p = os.path.join(EDGE, "white.png")
    Image.new("RGB", (400, 200), (255, 255, 255)).save(p)
    cases["blank white"] = p

    # tall narrow
    p = os.path.join(EDGE, "tall.png")
    Image.new("RGB", (64, 900), (255, 255, 255)).save(p)
    cases["tall narrow blank"] = p

    # single row of tiny text
    p = os.path.join(EDGE, "tiny.png")
    img = Image.new("RGB", (300, 24), (255, 255, 255))
    from PIL import ImageDraw, ImageFont
    f = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 14)
    ImageDraw.Draw(img).text((5, 3), "小字测试", font=f, fill=(0, 0, 0))
    img.save(p)
    cases["tiny text"] = p

    ok = 0
    for name, path in cases.items():
        out = os.path.join(HERE, "_edge", name.replace(" ", "_"))
        try:
            code, log = run(path, out)
        except subprocess.TimeoutExpired:
            print("%-18s TIMEOUT" % name)
            continue
        # A 1x1 image is legitimately rejected; anything else must succeed.
        crashed = "Traceback" in log
        expect_reject = name.startswith("1x1")
        if expect_reject:
            ok_case = (code == 2 and not crashed)
        else:
            ok_case = (code == 0 and not crashed)
        status = "OK" if ok_case else "CRASH"
        if ok_case:
            ok += 1
        print("%-18s exit=%-3d %s" % (name, code, status))
        if crashed:
            tail = [ln for ln in log.strip().splitlines() if ln.strip()][-2:]
            for ln in tail:
                print("      " + ln[:120])

    # missing file must fail cleanly
    code, log = run(os.path.join(EDGE, "does_not_exist.png"), os.path.join(HERE, "_edge", "missing"))
    clean = "Traceback" not in log
    print("%-18s exit=%-3d %s" % ("missing file", code, "OK" if clean else "CRASH"))
    ok += 1 if clean else 0

    print("--- %d/%d handled ---" % (ok, len(cases) + 1))
    return 0 if ok == len(cases) + 1 else 1


if __name__ == "__main__":
    sys.exit(main())
