#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WeChat XNet OCR - shared utilities.

Provides image generation, preprocessing to the raw NCHW float layout the
XNet runtime consumes, and CTC decoding against charset_zh13562.txt.
"""
import os
import sys
import json
import struct
import numpy as np

MODEL_DIR = os.environ.get("XNET_MODEL_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "WeChatOcr-8096")
CHARSET_PATH = os.path.join(MODEL_DIR, "charset_zh13562.txt")

# CTC blank index. The class count is 13564 while the character set holds
# 13563 entries, and decoded labels are consistently one above the expected
# character index - so the blank occupies class 0 and character i is class
# i+1. BLANK_INDEX_TRAILING is kept for comparison during calibration.
BLANK_INDEX = 0
BLANK_INDEX_TRAILING = 13563


def load_charset(path=CHARSET_PATH):
    """Return the character list, one entry per line.

    The file stores one character per line. Splitting on newlines (rather than
    iterating a decoded string) is required: multi-byte characters such as the
    CJK range would otherwise inflate the class count and misalign every index.
    """
    with open(path, "rb") as fh:
        raw = fh.read()
    text = raw.decode("utf-8")
    chars = [ln for ln in text.split("\n")]
    # A trailing newline yields one empty entry; drop trailing blanks only.
    while chars and chars[-1] == "":
        chars.pop()
    return chars


def read_text_lines(path):
    with open(path, "r", encoding="utf-8") as fh:
        return [ln.rstrip("\r\n") for ln in fh]


def render_line(text, height=64, font_path=r"C:\Windows\Fonts\msyh.ttc",
                font_size=None, padding=8, bg=255, fg=0):
    """Render a horizontal text line to a grayscale uint8 array."""
    from PIL import Image, ImageDraw, ImageFont
    if not os.path.exists(font_path):
        font_path = r"C:\Windows\Fonts\simhei.ttf"
    font_size = font_size or (height - 2 * padding)
    font = ImageFont.truetype(font_path, font_size)
    probe = Image.new("L", (8, 8), bg)
    drawer = ImageDraw.Draw(probe)
    box = drawer.textbbox((0, 0), text, font=font)
    width = max(1, box[2] - box[0] + 2 * padding)
    img = Image.new("L", (width, height), bg)
    drawer = ImageDraw.Draw(img)
    drawer.text((padding - box[0], (height - (box[3] - box[1])) // 2 - box[1]),
               text, font=font, fill=fg)
    return np.asarray(img, dtype=np.uint8)


def preprocess_gray(gray, target_h=32, mean=0.5, std=0.5):
    """Resize a grayscale image to a fixed height and normalise to NCHW float32.

    The recogniser consumes one channel (C=1) in NCHW order.
    """
    from PIL import Image
    h, w = gray.shape[:2]
    if h <= 0 or w <= 0:
        raise ValueError("empty image")
    scale = target_h / float(h)
    target_w = max(1, int(round(w * scale)))
    img = Image.fromarray(gray.astype(np.uint8), mode="L")
    img = img.resize((target_w, target_h), Image.BILINEAR)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    arr = (arr - mean) / std
    return arr.astype(np.float32).reshape(1, 1, target_h, target_w)


def preprocess_bgr(rgb, target_h=32, mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5)):
    """Resize an RGB image to a fixed height and normalise to NCHW float32."""
    from PIL import Image
    h, w = rgb.shape[:2]
    scale = target_h / float(h)
    target_w = max(1, int(round(w * scale)))
    img = Image.fromarray(rgb.astype(np.uint8), mode="RGB")
    img = img.resize((target_w, target_h), Image.BILINEAR)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    mean_arr = np.asarray(mean, dtype=np.float32).reshape(1, 1, 3)
    std_arr = np.asarray(std, dtype=np.float32).reshape(1, 1, 3)
    arr = (arr - mean_arr) / std_arr
    return arr.astype(np.float32).transpose(2, 0, 1).reshape(1, 3, target_h, target_w)


def write_raw_nchw(arr, out_path):
    """Write an NCHW float32 array with a small JSON sidecar describing shape."""
    arr = np.ascontiguousarray(arr, dtype=np.float32)
    with open(out_path, "wb") as fh:
        fh.write(arr.tobytes())
    n, c, h, w = arr.shape
    meta = {"shape": [int(n), int(c), int(h), int(w)], "dtype": "float32",
            "count": int(arr.size)}
    with open(out_path + ".json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    return meta


def read_raw_nchw(path):
    with open(path + ".json", "r", encoding="utf-8") as fh:
        meta = json.load(fh)
    shape = tuple(meta["shape"])
    with open(path, "rb") as fh:
        buf = fh.read()
    arr = np.frombuffer(buf, dtype=np.float32)
    if arr.size != int(np.prod(shape)):
        raise ValueError("raw size %d does not match shape %s" % (arr.size, shape))
    return arr.reshape(shape)


def read_output_bin(path, count):
    """Read a raw float32 output tensor dumped by the C++ runner."""
    with open(path, "rb") as fh:
        buf = fh.read()
    arr = np.frombuffer(buf, dtype=np.float32)
    if arr.size != count:
        raise ValueError("output size %d != expected %d" % (arr.size, count))
    return arr


def ctc_decode(probs, charset, blank=BLANK_INDEX, index_shift=1):
    """Greedy CTC decode.

    probs: array shaped (T, C) or (1, T, C) with class probabilities/logits.
    index_shift: class index offset to a character index. With the blank at
    class 0, character i lives at class i+1, so index_shift=1.
    Returns the decoded string and the per-step confidence.
    """
    if probs.ndim == 3:
        probs = probs[0]
    if probs.ndim != 2:
        raise ValueError("probs must be (T, C), got %s" % (probs.shape,))
    labels = np.argmax(probs, axis=1)
    out = []
    conf = []
    prev = -1
    for t, idx in enumerate(labels):
        if idx == blank:
            prev = idx
            continue
        if idx == prev:
            continue
        out.append(idx)
        conf.append(float(probs[t, idx]))
        prev = idx
    chars = []
    for idx in out:
        ci = idx - index_shift
        if 0 <= ci < len(charset):
            chars.append(charset[ci])
        else:
            chars.append("�")
    return "".join(chars), conf


def normalize_text(text, keep_inner_space=True):
    """Strip edge padding left by CTC and collapse repeated inner blanks.

    The character set contains a space glyph, so CTC may emit leading or
    trailing blanks from the line margins. Those are padding, not content.
    """
    text = text.strip()
    if keep_inner_space:
        collapsed = []
        prev_space = False
        for ch in text:
            if ch == " ":
                if prev_space:
                    continue
                prev_space = True
            else:
                prev_space = False
            collapsed.append(ch)
        return "".join(collapsed)
    return text.replace(" ", "")


def softmax_rows(x):
    x = x.astype(np.float64)
    x = x - x.max(axis=1, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=1, keepdims=True)
