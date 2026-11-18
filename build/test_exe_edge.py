#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Edge-case and format acceptance for the packaged exe.

Mirrors test_edge.py and test_extended.py, but drives the frozen ocr.exe under
a minimal PATH, so any packaging regression (Pillow plugin, numpy path, temp
writes) shows up here rather than only in the source tree.
"""
import json
import os
import subprocess
import sys
import time
from PIL import Image, ImageDraw, ImageFont

DIST = sys.argv[1] if len(sys.argv) > 1 else r"E:\ocr\build\ocr"
WORK = os.path.abspath(os.path.join(os.path.dirname(DIST.rstrip("\\")), "_exe_edge"))
MIN_PATH = os.pathsep.join([r"C:\Windows\system32", r"C:\Windows",
                            r"C:\Windows\System32\Wbem"])
FONT = r"C:\Windows\Fonts\msyh.ttc"


def env_min():
    env = dict(os.environ)
    env["PATH"] = MIN_PATH
    for k in ("XNET_WEIXIN_DIR", "XNET_MODEL_DIR", "XNET_TOOLS_DIR", "WEIXIN_ROOT"):
        env.pop(k, None)
    return env


def run(image, out, extra=None):
    cmd = [os.path.join(DIST, "ocr.exe"), image, "--out", out] + (extra or [])
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, env=env_min(),
                       errors="replace", timeout=1200)
    return p.returncode, p.stdout + p.stderr, time.time() - t0


def lines_of(out):
    rp = os.path.join(out, "result.json")
    if not os.path.isfile(rp):
        return None
    with open(rp, "r", encoding="utf-8") as fh:
        return [l["text"] for l in json.load(fh).get("lines", [])]


def make_edge_cases():
    d = os.path.join(WORK, "img")
    os.makedirs(d, exist_ok=True)
    cases = {}
    p = os.path.join(d, "px1.png")
    Image.new("RGB", (1, 1), (0, 0, 0)).save(p)
    cases["1x1 pixel"] = p
    p = os.path.join(d, "wide_thin.png")
    Image.new("RGB", (3000, 12), (255, 255, 255)).save(p)
    cases["wide thin blank"] = p
    p = os.path.join(d, "black.png")
    Image.new("RGB", (400, 200), (0, 0, 0)).save(p)
    cases["solid black"] = p
    p = os.path.join(d, "white.png")
    Image.new("RGB", (400, 200), (255, 255, 255)).save(p)
    cases["blank white"] = p
    p = os.path.join(d, "tall.png")
    Image.new("RGB", (64, 900), (255, 255, 255)).save(p)
    cases["tall narrow blank"] = p
    p = os.path.join(d, "tiny.png")
    img = Image.new("RGB", (300, 24), (255, 255, 255))
    f = ImageFont.truetype(FONT, 14)
    ImageDraw.Draw(img).text((5, 3), "小字测试", font=f, fill=(0, 0, 0))
    img.save(p)
    cases["tiny text"] = p
    return cases


def make_formats():
    d = os.path.join(WORK, "fmt")
    os.makedirs(d, exist_ok=True)
    img = Image.new("RGB", (820, 220), (255, 255, 255))
    dr = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, 40)
    dr.text((60, 50), "格式兼容性测试", font=f, fill=(25, 25, 25))
    dr.text((60, 140), "Format Compatibility 2024", font=f, fill=(25, 25, 25))
    out = {}
    for name, conv, fmt in [
        ("png_rgb", img.convert("RGB"), "PNG"),
        ("jpg_rgb", img.convert("RGB"), "JPEG"),
        ("bmp_rgb", img.convert("RGB"), "BMP"),
        ("png_rgba", img.convert("RGBA"), "PNG"),
        ("png_gray", img.convert("L"), "PNG"),
        ("tif_rgb", img.convert("RGB"), "TIFF"),
    ]:
        p = os.path.join(d, name + ".img")
        conv.save(p, format=fmt)
        out[name] = p
    return out


def main():
    os.makedirs(WORK, exist_ok=True)
    results = []

    print("--- edge cases ---")
    for name, path in make_edge_cases().items():
        out = os.path.join(WORK, "out_" + name.replace(" ", "_"))
        code, log, dt = run(path, out)
        crashed = "Traceback" in log
        expect_reject = name.startswith("1x1")
        ok = (code == 2 and not crashed) if expect_reject else (code == 0 and not crashed)
        results.append(("edge:" + name, ok))
        print("%-24s %s  exit=%d %.1fs" % (name, "PASS" if ok else "FAIL", code, dt))

    print("--- formats ---")
    for name, path in make_formats().items():
        out = os.path.join(WORK, "fmt_" + name)
        code, log, dt = run(path, out)
        lines = lines_of(out) or []
        joined = "".join(lines)
        ok = code == 0 and ("格式兼容性测试" in joined or "Format Compatibility 2024" in joined)
        results.append(("fmt:" + name, ok))
        print("%-24s %s  exit=%d %.1fs" % (name, "PASS" if ok else "FAIL", code, dt))

    print("--- no-text false positive ---")
    img = Image.new("RGB", (700, 400), (245, 246, 248))
    dr = ImageDraw.Draw(img)
    dr.ellipse((150, 100, 550, 300), fill=(190, 205, 220))
    dr.rectangle((100, 320, 600, 350), fill=(160, 175, 195))
    p = os.path.join(WORK, "notext.png")
    img.save(p)
    out = os.path.join(WORK, "out_notext")
    code, log, dt = run(p, out)
    junk = [t for t in (lines_of(out) or []) if t.strip()]
    ok = code == 0 and not junk
    results.append(("no_text_false_positive", ok))
    print("%-24s %s  exit=%d junk=%r" % ("no_text", "PASS" if ok else "FAIL", code, junk))

    print("--- large image + cold start ---")
    big = Image.new("RGB", (4000, 2600), (255, 255, 255))
    dr = ImageDraw.Draw(big)
    f = ImageFont.truetype(FONT, 60)
    for i in range(6):
        dr.text((120, 140 + i * 380), "大图测试第%d行 LargeImage" % (i + 1), font=f, fill=(20, 20, 20))
    p = os.path.join(WORK, "large.png")
    big.save(p)
    out = os.path.join(WORK, "out_large")
    code, log, dt = run(p, out)
    lines = lines_of(out) or []
    ok = code == 0 and len(lines) >= 6 and all(("大图测试第%d" % (i + 1)) in lines[i]
                                              for i in range(6))
    results.append(("large_4000x2600", ok))
    print("%-24s %s  exit=%d %.1fs lines=%d" % ("large image", "PASS" if ok else "FAIL",
                                                code, dt, len(lines)))

    passed = sum(1 for _, ok in results if ok)
    print("--- packaged exe edge/format: %d/%d passed ---" % (passed, len(results)))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
