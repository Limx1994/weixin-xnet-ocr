#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate detector post-processing against rendered text boxes."""
import sys
import os
import json
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import xnet_ocr_lib as lib
import det_postprocess as dpp
from make_input import write_input_nchw
from calibrate_det import make_scene, run_det, load_score, FONT

DET_MODEL = os.path.join(lib.MODEL_DIR, "text_det_fp16_v2.xnet")
WORK = os.path.join(HERE, "_detcalib")


def iou(a, b):
    pa = np.asarray(a, dtype=np.float64).reshape(4, 2)
    pb = np.asarray(b, dtype=np.float64).reshape(2, 2)
    ax0, ay0 = pa[:, 0].min(), pa[:, 1].min()
    ax1, ay1 = pa[:, 0].max(), pa[:, 1].max()
    bx0, by0 = pb[0, 0], pb[0, 1]
    bx1, by1 = pb[1, 0], pb[1, 1]
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    areaA = (ax1 - ax0) * (ay1 - ay0)
    areaB = (bx1 - bx0) * (by1 - by0)
    return inter / max(1e-9, areaA + areaB - inter)


def main():
    os.makedirs(WORK, exist_ok=True)
    out_dir = os.path.join(WORK, "out")
    os.makedirs(out_dir, exist_ok=True)
    lines = ["微信图片文字提取", "OCR识别测试", "Hello WeChat 2024"]
    gray, gt_boxes = make_scene(lines)
    h, w = gray.shape

    from calibrate_det import preprocess
    arr, hw = preprocess(gray, target_long=640, mean=0.5, std=0.5)
    bin_path = os.path.join(WORK, "in.bin")
    write_input_nchw(arr, bin_path)
    code, log = run_det(bin_path, out_dir)
    if code != 0:
        print("infer failed 0x%x" % (code & 0xFFFFFFFF))
        return 1

    score = load_score(out_dir)
    with open(os.path.join(out_dir, "kernel_map.json"), "r", encoding="utf-8") as fh:
        kmeta = json.load(fh)
    kernel = lib.read_output_bin(os.path.join(out_dir, "kernel_map.bin"),
                                 int(np.prod(kmeta["dims"]))).reshape(kmeta["dims"])
    print("score=%s kernel=%s" % (score.shape, kernel.shape))

    # Keep these identical to ocr_image.detect() so this script stays a valid
    # regression check for the shipping parameters.
    import ocr_image as ocr
    prob, quads = dpp.recover_quads(score, kernel, thresh=0.3, min_area=40,
                                    box_thresh=0.2, unclip_ratio=2.0)
    boxes = dpp.scale_boxes(quads, (h, w), (score.shape[0], score.shape[1]))
    print("recovered %d boxes" % len(boxes))
    for b in boxes:
        pts = np.asarray(b).reshape(4, 2)
        print("  box x[%.1f..%.1f] y[%.1f..%.1f]" %
              (pts[:, 0].min(), pts[:, 0].max(), pts[:, 1].min(), pts[:, 1].max()))

    # Match each ground-truth line to the best recovered box.
    matched = 0
    for i, gt in enumerate(gt_boxes):
        best, bi = 0.0, -1
        for j, b in enumerate(boxes):
            v = iou(b, gt)
            if v > best:
                best, bi = v, j
        ok = best > 0.5
        matched += 1 if ok else 0
        print("gt%d box=%s best_iou=%.3f -> box%s %s" %
              (i, gt, best, bi, "MATCH" if ok else "miss"))
    print("matched %d/%d" % (matched, len(gt_boxes)))
    return 0 if matched == len(gt_boxes) else 1


if __name__ == "__main__":
    sys.exit(main())
