#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detector parameter margin check.

Runs the detector over the acceptance scenes for a grid of post-processing
parameters and reports how many expected lines each setting recovers. The
shipped defaults are considered safe only if neighbouring settings also work,
i.e. the chosen values are not on a knife edge.
"""
import sys
import os
import json
import itertools
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import xnet_ocr_lib as lib
import det_postprocess as dpp
import ocr_image as ocr

CASES_DIR = os.path.join(HERE, "test_images")


def load_score(out_dir):
    with open(os.path.join(out_dir, "score_map.json"), "r", encoding="utf-8") as fh:
        meta = json.load(fh)
    arr = lib.read_output_bin(os.path.join(out_dir, "score_map.bin"),
                              int(np.prod(meta["dims"]))).reshape(meta["dims"])
    return arr[0] if arr.ndim == 3 else arr


def main():
    with open(os.path.join(CASES_DIR, "manifest.json"), "r", encoding="utf-8") as fh:
        manifest = json.load(fh)

    # Reuse detector outputs already produced by the acceptance run when
    # available; otherwise run the detector once per case.
    cache_root = os.path.join(HERE, "_margin")
    os.makedirs(cache_root, exist_ok=True)

    cases = {}
    for name in ("plain", "dense_lines", "small_text", "long_line", "single_char"):
        gray = np.asarray(Image.open(manifest[name]["path"]).convert("L"), dtype=np.uint8)
        out = os.path.join(cache_root, name)
        os.makedirs(out, exist_ok=True)
        acc = os.path.join(HERE, "_accept", name, "det_out")
        score = kernel = None
        if os.path.exists(os.path.join(acc, "score_map.json")):
            try:
                score = load_score(acc)
                kp = os.path.join(acc, "kernel_map.json")
                if os.path.exists(kp):
                    with open(kp, "r", encoding="utf-8") as fh:
                        km = json.load(fh)
                    kernel = lib.read_output_bin(
                        os.path.join(acc, "kernel_map.bin"),
                        int(np.prod(km["dims"]))).reshape(km["dims"])
            except Exception:
                score = kernel = None
        if score is None:
            boxes, score, prob = ocr.detect(gray, out, long_side=960)
            acc = os.path.join(out, "det_out")
            score = load_score(acc)
            kp = os.path.join(acc, "kernel_map.json")
            kernel = None
            if os.path.exists(kp):
                with open(kp, "r", encoding="utf-8") as fh:
                    km = json.load(fh)
                kernel = lib.read_output_bin(
                    os.path.join(acc, "kernel_map.bin"),
                    int(np.prod(km["dims"]))).reshape(km["dims"])
        cases[name] = {
            "score": score,
            "kernel": kernel,
            "src_hw": gray.shape,
            "expected": len(manifest[name]["expected"]),
        }

    grid = list(itertools.product([0.2, 0.3, 0.4], [20, 40, 80], [0.15, 0.2, 0.3], [1.5, 2.0, 2.5]))
    print("cases: %s" % {k: v["expected"] for k, v in cases.items()})
    print("grid: %d settings" % len(grid))

    worst = []
    for thresh, min_area, box_thresh, unclip in grid:
        total_ratio = 0.0
        detail = {}
        for name, c in cases.items():
            try:
                _, quads = dpp.recover_quads(c["score"], c["kernel"], thresh=thresh,
                                             min_area=min_area, box_thresh=box_thresh,
                                             unclip_ratio=unclip)
            except Exception:
                quads = []
            ratio = len(quads) / float(max(1, c["expected"]))
            detail[name] = len(quads)
            total_ratio += min(ratio, 1.5)
        avg = total_ratio / len(cases)
        worst.append((avg, thresh, min_area, box_thresh, unclip, detail))

    worst.sort(reverse=True)
    print("--- top 6 settings by mean recall (capped 1.5) ---")
    for avg, th, ma, bt, uc, detail in worst[:6]:
        print("thresh=%.1f min_area=%-3d box=%.2f unclip=%.1f avg=%.3f %s" %
              (th, ma, bt, uc, avg, detail))
    # Where does the shipped default sit?
    for avg, th, ma, bt, uc, detail in worst:
        if (th, ma, bt, uc) == (0.3, 40, 0.2, 2.0):
            rank = worst.index((avg, th, ma, bt, uc, detail)) + 1
            print("shipped default (0.3, 40, 0.2, 2.0): avg=%.3f rank=%d/%d %s" %
                  (avg, rank, len(worst), detail))
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
