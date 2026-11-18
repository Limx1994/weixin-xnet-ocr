#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Calibrate the detector: does score_map respond over the text regions?"""
import sys
import os
import json
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
WEIXIN_DIR = paths.weixin_dir() or ""
import xnet_ocr_lib as lib
from make_input import write_input_nchw

DET_MODEL = os.path.join(lib.MODEL_DIR, "text_det_fp16_v2.xnet")
WORK = os.path.join(HERE, "_detcalib")
FONT = r"C:\Windows\Fonts\msyh.ttc"


def make_scene(lines, width=640, line_h=64, pad=40):
    """Render several text lines on white; return image and line boxes."""
    height = pad * 2 + line_h * len(lines)
    img = Image.new("L", (width, height), 255)
    drawer = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, int(line_h * 0.6))
    boxes = []
    for i, text in enumerate(lines):
        y = pad + i * line_h
        box = drawer.textbbox((0, 0), text, font=font)
        tw = box[2] - box[0]
        x = max(pad, (width - tw) // 2)
        drawer.text((x, y), text, font=font, fill=0)
        boxes.append([x, y, x + tw, y + int(line_h * 0.75)])
    return np.asarray(img, dtype=np.uint8), boxes


def preprocess(gray, target_long=960, mean=0.5, std=0.5, limit_type="max",
               align=32):
    """Resize keeping aspect ratio; round both sides up to a multiple of align.

    The detector requires the height to be a multiple of 32 (272 fails, 256
    and 320 succeed), so sides are padded by rounding up.
    """
    h, w = gray.shape[:2]
    scale = target_long / float(max(h, w) if limit_type == "max" else min(h, w))
    scale = min(scale, 1.0) if limit_type == "max" else scale
    nh = int(np.ceil(h * scale / align) * align)
    nw = int(np.ceil(w * scale / align) * align)
    img = Image.fromarray(gray.astype(np.uint8), mode="L").resize((nw, nh), Image.BILINEAR)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    arr = (arr - mean) / std
    rgb = np.stack([arr, arr, arr], axis=2)
    return rgb.transpose(2, 0, 1).reshape(1, 3, nh, nw).astype(np.float32), (nh, nw)


def run_det(bin_path, out_dir):
    env = dict(os.environ)
    env["PATH"] = WEIXIN_DIR + os.pathsep + env.get("PATH", "")
    proc = subprocess.run([paths.infer_exe(), DET_MODEL, bin_path, out_dir, "11"],
                          capture_output=True, text=True, env=env,
                          errors="replace", timeout=300)
    return proc.returncode, proc.stdout + proc.stderr


def load_score(out_dir):
    with open(os.path.join(out_dir, "score_map.json"), "r", encoding="utf-8") as fh:
        meta = json.load(fh)
    arr = lib.read_output_bin(os.path.join(out_dir, "score_map.bin"),
                              int(np.prod(meta["dims"]))).reshape(meta["dims"])
    return arr[0] if arr.ndim == 3 else arr


def box_overlap_stats(score, boxes, in_hw, thresh=0.3):
    """Compare mean response inside boxes vs outside."""
    h, w = score.shape
    mask = np.zeros((h, w), dtype=bool)
    for (x0, y0, x1, y1) in boxes:
        px0, py0 = int(x0 * w / in_hw[1]), int(y0 * h / in_hw[0])
        px1, py1 = int(x1 * w / in_hw[1]), int(y1 * h / in_hw[0])
        px0, py0 = max(0, px0), max(0, py0)
        px1, py1 = min(w, px1), min(h, py1)
        if px1 > px0 and py1 > py0:
            mask[py0:py1, px0:px1] = True
    binary = score > thresh
    inside = score[mask]
    outside = score[~mask]
    return {
        "in_mean": float(inside.mean()) if inside.size else 0.0,
        "out_mean": float(outside.mean()) if outside.size else 0.0,
        "in_max": float(inside.max()) if inside.size else 0.0,
        "global_max": float(score.max()),
        "ratio": float(inside.mean() / outside.mean()) if outside.size and outside.mean() > 0 else 0.0,
        "hit_pixels": int(binary[mask].sum()),
        "in_pixels": int(mask.sum()),
    }


def main():
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(os.path.join(WORK, "out"), exist_ok=True)
    lines = ["微信图片文字提取", "OCR识别测试", "Hello WeChat 2024"]
    gray, boxes = make_scene(lines)
    print("scene %s boxes=%s" % (gray.shape, boxes))

    for long_side in (640, 960):
        for mean, std in [(0.5, 0.5), (0.485, 0.229)]:
            arr, hw = preprocess(gray, target_long=long_side, mean=mean, std=std)
            bin_path = os.path.join(WORK, "in.bin")
            write_input_nchw(arr, bin_path)
            code, log = run_det(bin_path, os.path.join(WORK, "out"))
            if code != 0:
                print("long=%d mean=%.3f infer fail 0x%x" % (long_side, mean, code & 0xFFFFFFFF))
                continue
            score = load_score(os.path.join(WORK, "out"))
            stats = box_overlap_stats(score, boxes, (hw[0], hw[1]))
            print("long=%d mean=%.3f std=%.3f score%s in_mean=%.4f out_mean=%.4f ratio=%.2f in_max=%.4f gmax=%.4f hit=%d/%d" %
                  (long_side, mean, std, score.shape, stats["in_mean"], stats["out_mean"],
                   stats["ratio"], stats["in_max"], stats["global_max"],
                   stats["hit_pixels"], stats["in_pixels"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
