#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Calibrate recogniser preprocessing.

Generates text-line images, preprocesses them under several parameter sets,
runs each through the XNet recogniser, and reports CTC-decoded text plus the
mean top-1 confidence. The parameter set that reproduces the expected text with
the highest confidence wins.
"""
import sys
import os
import json
import subprocess
import itertools
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
WEIXIN_DIR = paths.weixin_dir() or ""
import xnet_ocr_lib as lib
from make_input import write_input_nchw

MODEL = os.path.join(lib.MODEL_DIR, "text_rec_zh13562_fp16_v2.xnet")
WORK = os.path.join(HERE, "_calib")

CASES = [
    "Hello123",
    "微信OCR测试",
    "PaddlePaddle2024",
    "文本识别准确率",
]


def run_infer(bin_path, out_dir):
    env = dict(os.environ)
    env["PATH"] = WEIXIN_DIR + os.pathsep + env.get("PATH", "")
    proc = subprocess.run(
        [paths.infer_exe(), MODEL, bin_path, out_dir, "11"],
        capture_output=True, text=True, env=env, errors="replace", timeout=300)
    return proc.returncode, proc.stdout + proc.stderr


def evaluate(params, target_h=32):
    """Return list of (case, decoded, confidence, match)."""
    mean, std, invert, interp = params
    results = []
    for text in CASES:
        gray = lib.render_line(text, height=64)
        if invert:
            gray = 255 - gray
        from PIL import Image, ImageDraw, ImageFont
        h, w = gray.shape[:2]
        scale = target_h / float(h)
        tw = max(1, int(round(w * scale)))
        resample = Image.BILINEAR if interp == "bilinear" else Image.BICUBIC
        img = Image.fromarray(gray.astype(np.uint8), mode="L").resize((tw, target_h), resample)
        arr = np.asarray(img, dtype=np.float32) / 255.0
        arr = (arr - mean) / std
        rgb = np.stack([arr, arr, arr], axis=2)
        nchw = rgb.transpose(2, 0, 1).reshape(1, 3, target_h, tw).astype(np.float32)

        bin_path = os.path.join(WORK, "in.bin")
        out_dir = os.path.join(WORK, "out")
        os.makedirs(out_dir, exist_ok=True)
        write_input_nchw(nchw, bin_path)
        code, log = run_infer(bin_path, out_dir)
        if code != 0:
            results.append((text, "<infer-fail:0x%x>" % (code & 0xFFFFFFFF), 0.0, False))
            continue
        charset = lib.load_charset()
        with open(os.path.join(out_dir, "output.json"), "r", encoding="utf-8") as fh:
            meta = json.load(fh)
        arr_out = lib.read_output_bin(os.path.join(out_dir, "output.bin"),
                                      int(np.prod(meta["dims"]))).reshape(meta["dims"])
        probs = lib.softmax_rows(arr_out[0])
        decoded, conf = lib.ctc_decode(probs, charset)
        score = (sum(conf) / len(conf)) if conf else 0.0
        results.append((text, decoded, score, decoded == text))
    return results


def main():
    os.makedirs(WORK, exist_ok=True)
    grids = []
    for mean, std in [(0.5, 0.5), (0.485, 0.229), (0.0, 1.0), (127.5 / 255.0, 127.5 / 255.0)]:
        for invert in (False, True):
            for interp in ("bilinear", "bicubic"):
                grids.append((mean, std, invert, interp))

    print("charset=%d  cases=%d  configs=%d" % (len(lib.load_charset()), len(CASES), len(grids)))
    best = None
    for params in grids:
        try:
            res = evaluate(params)
        except Exception as exc:
            print("config %s error: %s" % (params, exc))
            continue
        matches = sum(1 for r in res if r[3])
        avg_conf = sum(r[2] for r in res) / len(res)
        print("mean=%.4f std=%.4f invert=%s interp=%-8s match=%d/%d avgconf=%.4f" %
              (params[0], params[1], params[2], params[3], matches, len(res), avg_conf))
        for text, dec, score, ok in res:
            print("    %-16r -> %-18r %.4f %s" % (text, dec, score, "OK" if ok else ""))
        if best is None or (matches, avg_conf) > (best[1], best[2]):
            best = (params, matches, avg_conf)
    print("best: %s match=%d avgconf=%.4f" % (best[0], best[1], best[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
