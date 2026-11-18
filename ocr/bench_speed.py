#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Measure OCR throughput: end-to-end and per-stage timings.

Reports wall-clock per stage (decode/preprocess/detect/crop/recognise/decode)
so the bottleneck is identifiable, plus characters-per-second.
"""
import sys
import os
import json
import time
import subprocess
import argparse
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
WEIXIN_DIR = paths.weixin_dir() or ""
import ocr_image as ocr
import xnet_ocr_lib as lib



def stage_run(path, long_side, repeats):
    """Time each pipeline stage separately."""
    env = dict(os.environ)
    env["PATH"] = WEIXIN_DIR + os.pathsep + env.get("PATH", "")

    # image decode
    t0 = time.time()
    img = Image.open(path).convert("L")
    gray = np.asarray(img, dtype=np.uint8)
    t_decode = time.time() - t0

    acc = {"detect": 0.0, "crop": 0.0, "recognise": 0.0, "n_lines": 0, "chars": 0}
    total = 0.0
    for k in range(repeats):
        out = os.path.join(HERE, "_speed", "run%d" % k)
        os.makedirs(out, exist_ok=True)
        t0 = time.time()
        boxes, score, prob = ocr.detect(gray, out, long_side=long_side)
        t1 = time.time()
        acc["detect"] += t1 - t0
        texts = []
        for i, quad in enumerate(ocr.sort_boxes(boxes)):
            t2 = time.time()
            strip = ocr.crop_line(gray, quad)
            t3 = time.time()
            acc["crop"] += t3 - t2
            text, conf = ocr.recognize(strip, out, i)
            t4 = time.time()
            acc["recognise"] += t4 - t3
            texts.append(text)
        total += time.time() - t0
        if k == 0:
            acc["n_lines"] = len(boxes)
            acc["chars"] = sum(len(t) for t in texts)
    return t_decode, acc, total / repeats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--long", type=int, default=960)
    ap.add_argument("-n", type=int, default=3, help="repeats")
    ap.add_argument("--cases", default="")
    args = ap.parse_args()

    manifest_path = os.path.join(HERE, "test_images", "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    names = args.cases.split(",") if args.cases else [
        "plain", "dense_lines", "small_text", "long_line", "single_char"]

    print("repeats=%d  long_side=%d" % (args.n, args.long))
    print("%-14s %8s %8s %8s %8s %8s %7s" %
          ("case", "decode", "detect", "crop", "recogn", "total", "char/s"))
    for name in names:
        if name not in manifest:
            continue
        t_decode, acc, avg = stage_run(manifest[name]["path"], args.long, args.n)
        chars = max(1, acc["chars"])
        print("%-14s %8.3f %8.3f %8.3f %8.3f %8.3f %7.1f" %
              (name, t_decode, acc["detect"] / args.n, acc["crop"] / args.n,
               acc["recognise"] / args.n, avg, chars / avg))
    return 0


if __name__ == "__main__":
    sys.exit(main())
