#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-end WeChat XNet OCR: image -> text.

Pipeline:
  1. read an image (grayscale), letterbox-resize to the detector's long side
     with both sides rounded up to a multiple of 32;
  2. run text_det_fp16_v2.xnet and recover text boxes;
  3. for each box, crop the line, resize to height 32, run
     text_rec_zh13562_fp16_v2.xnet and CTC-decode against charset_zh13562.txt;
  4. merge lines top-to-bottom and print the result.

usage: python ocr_image.py <image.png|jpg|bmp> [--long N] [--out dir]
"""
import sys
import os
import json
import argparse
import subprocess
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import xnet_ocr_lib as lib
import det_postprocess as dpp
import paths
from make_input import write_input_nchw

MODEL_DIR = paths.model_dir()
DET_MODEL = paths.require("detection model",
                          os.path.join(MODEL_DIR, "text_det_fp16_v2.xnet"))
REC_MODEL = paths.require("recognition model",
                          os.path.join(MODEL_DIR, "text_rec_zh13562_fp16_v2.xnet"))
INFER = paths.require("inference driver", paths.infer_exe())
WEIXIN_DIR = paths.weixin_dir() or ""


def run_infer(model, bin_path, out_dir):
    env = dict(os.environ)
    if WEIXIN_DIR:
        env["PATH"] = WEIXIN_DIR + os.pathsep + env.get("PATH", "")
    os.makedirs(out_dir, exist_ok=True)
    proc = subprocess.run([INFER, model, bin_path, out_dir, "11"],
                          capture_output=True, text=True, env=env,
                          errors="replace", timeout=600)
    return proc.returncode, proc.stdout + proc.stderr


def det_preprocess(gray, long_side=960, mean=0.5, std=0.5, align=32):
    h, w = gray.shape[:2]
    scale = min(long_side / float(max(h, w)), 1.0)
    nh = int(np.ceil(h * scale / align) * align)
    nw = int(np.ceil(w * scale / align) * align)
    img = Image.fromarray(gray.astype(np.uint8), mode="L").resize((nw, nh), Image.BILINEAR)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    arr = (arr - mean) / std
    rgb = np.stack([arr, arr, arr], axis=2)
    return rgb.transpose(2, 0, 1).reshape(1, 3, nh, nw).astype(np.float32), (h, w), (nh, nw)


def detect(gray, work, long_side=960):
    arr, src_hw, dst_hw = det_preprocess(gray, long_side=long_side)
    bin_path = os.path.join(work, "det_in.bin")
    write_input_nchw(arr, bin_path)
    out_dir = os.path.join(work, "det_out")
    code, log = run_infer(DET_MODEL, bin_path, out_dir)
    if code != 0:
        raise RuntimeError("detector failed 0x%x\n%s" % (code & 0xFFFFFFFF, log[-800:]))

    def load(name):
        with open(os.path.join(out_dir, name + ".json"), "r", encoding="utf-8") as fh:
            meta = json.load(fh)
        arr2 = lib.read_output_bin(os.path.join(out_dir, name + ".bin"),
                                   int(np.prod(meta["dims"]))).reshape(meta["dims"])
        return arr2

    score = load("score_map")
    if score.ndim == 3:
        score = score[0]
    try:
        kernel = load("kernel_map")
    except Exception:
        kernel = None

    prob, quads = dpp.recover_quads(score, kernel, thresh=0.3, min_area=40,
                                    box_thresh=0.2, unclip_ratio=2.0)
    boxes = dpp.scale_boxes(quads, src_hw, (score.shape[0], score.shape[1]))
    boxes = _filter_boxes(boxes, score.shape)
    if not boxes:
        print("no text detected (score_map max %.4f)" % float(score.max()))
    return boxes, score, prob


def _filter_boxes(boxes, score_hw):
    """Drop detections whose shape cannot be a horizontal text line.

    The detector occasionally fires on random texture. Such boxes are
    typically near-square or taller than wide, whereas a text line is wider
    than it is tall; extremely large boxes cover most of the image and are
    usually texture blobs rather than a line.
    """
    sh, sw = score_hw
    out = []
    for b in boxes:
        pts = np.asarray(b, dtype=np.float64).reshape(4, 2)
        w = float(pts[:, 0].max() - pts[:, 0].min())
        h = float(pts[:, 1].max() - pts[:, 1].min())
        if h <= 0:
            continue
        if h > w * 1.2:
            continue
        if w * h > 0.6 * sh * sw:
            continue
        out.append(b)
    return out


def crop_line(gray, quad):
    """Perspective-crop a quadrilateral line into an axis-aligned strip.

    Corners are assigned by geometry: the top edge joins the two points with
    the smallest y, the bottom edge the two with the largest y, and each pair
    is ordered by x. This is robust to the vertex ordering produced by the
    minimum-area-rectangle fit.
    """
    pts = np.asarray(quad, dtype=np.float64).reshape(4, 2)
    gh, gw = gray.shape
    # The unclip step can push corners outside the image. Clamp them so the
    # perspective sample stays inside the source; otherwise the strip is
    # stretched and the trailing glyphs are lost.
    pts[:, 0] = np.clip(pts[:, 0], 0.0, gw - 1.0)
    pts[:, 1] = np.clip(pts[:, 1], 0.0, gh - 1.0)

    by_y = np.argsort(pts[:, 1], kind="stable")
    top_pair = pts[by_y[:2]]
    bot_pair = pts[by_y[2:]]
    top_pair = top_pair[np.argsort(top_pair[:, 0], kind="stable")]
    bot_pair = bot_pair[np.argsort(bot_pair[:, 0], kind="stable")]
    tl, tr = top_pair[0], top_pair[1]
    bl, br = bot_pair[0], bot_pair[1]

    top_w = max(1.0, float(np.hypot(*(tr - tl))))
    bot_w = max(1.0, float(np.hypot(*(br - bl))))
    left_h = max(1.0, float(np.hypot(*(bl - tl))))
    right_h = max(1.0, float(np.hypot(*(br - tr))))
    dst_w = int(min(4096, max(8, round(max(top_w, bot_w)))))
    dst_h = int(min(256, max(8, round(max(left_h, right_h)))))

    src = np.array([tl, tr, br, bl], dtype=np.float32)
    dst = np.array([[0, 0], [dst_w - 1, 0], [dst_w - 1, dst_h - 1], [0, dst_h - 1]],
                   dtype=np.float32)
    fwd = _perspective_coeffs(src, dst)

    out = np.zeros((dst_h, dst_w), dtype=np.uint8)
    gh, gw = gray.shape
    for y in range(dst_h):
        for x in range(dst_w):
            den = fwd[6] * x + fwd[7] * y + 1.0
            if abs(den) < 1e-12:
                continue
            sx = (fwd[0] * x + fwd[1] * y + fwd[2]) / den
            sy = (fwd[3] * x + fwd[4] * y + fwd[5]) / den
            ix, iy = int(round(sx)), int(round(sy))
            if 0 <= ix < gw and 0 <= iy < gh:
                out[y, x] = gray[iy, ix]
    return out


def _perspective_coeffs(src, dst):
    """Solve coefficients that map destination pixels back to source pixels.

    Sampling needs the inverse direction: for a destination pixel (u, v) the
    source coordinate is
        x = (a*u + b*v + c) / (g*u + h*v + 1)
        y = (d*u + e*v + f) / (g*u + h*v + 1)
    so the linear system is built from the destination-to-source pairs.
    """
    a = []
    b = []
    for (u, v), (x, y) in zip(dst, src):
        a.append([u, v, 1.0, 0.0, 0.0, 0.0, -x * u, -x * v])
        b.append(x)
        a.append([0.0, 0.0, 0.0, u, v, 1.0, -y * u, -y * v])
        b.append(y)
    return np.linalg.solve(np.asarray(a, dtype=np.float64),
                           np.asarray(b, dtype=np.float64))


def recognize(gray_line, work, idx, mean=0.5, std=0.5, target_h=32,
              max_steps=90):
    """Recognise one text strip.

    The recogniser only accepts an input height of 32 (48 and above fail
    inside the engine), and it advances one CTC step per 4 input pixels, so a
    strip wider than the step budget is split at inter-glyph gaps and the
    per-segment results are concatenated. Narrow strips are padded with white
    margins because a bare glyph only a few pixels wide decodes unreliably.
    """
    h, w = gray_line.shape[:2]
    if h <= 0 or w <= 0:
        return "", 0.0

    # Trim to the ink extent first. The detector's unclip expansion can leave
    # wide blank margins; if they survive into the resize, the glyph shrinks
    # and the CTC head misreads it. Trimming never removes ink, so no text is
    # lost - only empty margin.
    cols = np.nonzero((gray_line < 200).sum(axis=0))[0]
    rows = np.nonzero((gray_line < 200).sum(axis=1))[0]
    if len(cols) and len(rows):
        gray_line = gray_line[max(0, rows[0] - 2):rows[-1] + 3,
                              max(0, cols[0] - 2):cols[-1] + 3]
        h, w = gray_line.shape[:2]
    if w < 8:
        return "", 0.0

    max_w = max(64, int(target_h * max_steps / 4))
    if w > max_w:
        return _recognize_segments(gray_line, work, idx, mean, std, target_h, max_w)

    if w < 96:
        margin = max(2, (96 - w) // 2)
        padded = np.full((h + 2 * margin, w + 2 * margin), 255, dtype=np.uint8)
        padded[margin:margin + h, margin:margin + w] = gray_line
        gray_line = padded
    return _recognize_one(gray_line, work, idx, mean, std, target_h)


def _recognize_segments(gray_line, work, idx, mean, std, target_h, max_w):
    """Recognise a wide strip by cutting it at inter-character gaps.

    Fixed windows cut through glyphs and the engine then misreads the
    straddled characters, which makes string-level stitching unreliable. Cutting
    at empty columns keeps every glyph whole, so the per-segment results can be
    concatenated directly.
    """
    h, w = gray_line.shape[:2]
    cuts = _plan_cuts(gray_line, max_w)
    pieces = []
    start = 0
    for end in cuts + [w]:
        if end <= start:
            continue
        chunk = gray_line[:, start:end]
        # A trailing sliver is still real text; pad it rather than drop it.
        if chunk.shape[1] < 8:
            pad = 8 - chunk.shape[1]
            chunk = np.pad(chunk, ((0, 0), (0, pad)), constant_values=255)
        text, _ = _recognize_one(chunk, work, idx * 1000 + len(pieces),
                                 mean, std, target_h)
        if text.strip():
            pieces.append(text.strip())
        start = end
    return "".join(pieces), 0.0


def _plan_cuts(gray_line, max_w):
    """Choose cut columns on inter-glyph gaps, dividing the line evenly.

    Measured on this engine: one CTC step covers about a quarter of a Chinese
    glyph, so a segment of width W gives W/4 steps and decodes roughly W/16
    glyphs. budget is therefore set to keep segments at about 8 glyphs
    (max_w * 0.18, i.e. ~130 px for the default budget). Cutting only in blank
    columns keeps every glyph whole, which is what makes plain concatenation of
    the segment results safe.
    """
    h, w = gray_line.shape[:2]
    budget = max(64, int(max_w * 0.18))
    n_seg = max(2, int(np.ceil(w / float(budget))))
    target_w = int(np.ceil(w / float(n_seg)))

    ink = (gray_line < 200).sum(axis=0)
    bands = []
    start = None
    for x in range(w):
        if ink[x] > 0 and start is None:
            start = x
        elif ink[x] == 0 and start is not None:
            bands.append((start, x - 1))
            start = None
    if start is not None:
        bands.append((start, w - 1))
    if not bands:
        return []

    # Candidate cuts are midpoints of blank-column gaps between ink bands, so a
    # cut never splits a glyph.
    gaps = []
    for i in range(1, len(bands)):
        gap_lo = bands[i - 1][1]
        gap_hi = bands[i][0]
        if gap_hi > gap_lo:
            gaps.append((gap_lo + gap_hi) // 2)
    if not gaps:
        # No blank column anywhere (e.g. underlined or touching glyphs). Fall
        # back to hard cuts at the planned edges so the segment width still
        # respects the step budget instead of silently truncating the line.
        return [min(w - 1, target_w * k) for k in range(1, n_seg)]

    # Walk the line, cutting at the gap nearest each evenly spaced edge.
    cuts = []
    prev = 0
    for k in range(1, n_seg):
        edge = target_w * k
        best = None
        for cand in gaps:
            if cand <= prev:
                continue
            if best is None or abs(cand - edge) < abs(best - edge):
                best = cand
        if best is None or best - prev < 24:
            # No usable gap at this edge; fall back to the planned edge so the
            # following segment is not left wider than the step budget.
            best = min(w - 1, edge)
            if best <= prev:
                continue
        cuts.append(best)
        prev = best

    out = []
    for c in cuts:
        if not out or c > out[-1]:
            out.append(c)
    return out


def _recognize_one(gray_line, work, idx, mean, std, target_h):
    arr = lib.preprocess_gray(gray_line, target_h=target_h, mean=mean, std=std)
    rgb = np.concatenate([arr, arr, arr], axis=1)
    bin_path = os.path.join(work, "rec_in_%d.bin" % idx)
    write_input_nchw(rgb, bin_path)
    out_dir = os.path.join(work, "rec_out_%d" % idx)
    code, log = run_infer(REC_MODEL, bin_path, out_dir)
    if code != 0:
        return "", 0.0
    with open(os.path.join(out_dir, "output.json"), "r", encoding="utf-8") as fh:
        meta = json.load(fh)
    arr2 = lib.read_output_bin(os.path.join(out_dir, "output.bin"),
                               int(np.prod(meta["dims"]))).reshape(meta["dims"])
    charset = lib.load_charset()
    probs = lib.softmax_rows(arr2[0])
    text, conf = lib.ctc_decode(probs, charset)
    score = (sum(conf) / len(conf)) if conf else 0.0
    return text, score


def _merge_segments(texts):
    """Concatenate overlapping segments, dropping duplicated tail/head."""
    out = ""
    for t in texts:
        t = t.strip()
        if not t:
            continue
        if not out:
            out = t
            continue
        # Remove the longest suffix of `out` that is a prefix of `t`.
        best = 0
        limit = min(len(out), len(t))
        for k in range(limit, 0, -1):
            if out.endswith(t[:k]):
                best = k
                break
        out += t[best:]
    return out


def sort_boxes(boxes):
    """Top-to-bottom, then left-to-right."""
    def key(b):
        pts = np.asarray(b).reshape(4, 2)
        return (round(pts[:, 1].mean() / 20.0), pts[:, 0].min())
    return sorted(boxes, key=key)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--long", type=int, default=960)
    ap.add_argument("--out", default=os.path.join(HERE, "_ocr_out"))
    args = ap.parse_args()

    if not os.path.exists(args.image):
        print("error: image not found: %s" % args.image, file=sys.stderr)
        return 2
    os.makedirs(args.out, exist_ok=True)
    try:
        img = Image.open(args.image).convert("L")
    except Exception as exc:
        print("error: cannot read image %s: %s" % (args.image, exc), file=sys.stderr)
        return 2
    gray = np.asarray(img, dtype=np.uint8)
    if gray.size == 0 or gray.shape[0] < 4 or gray.shape[1] < 4:
        print("error: image too small: %s" % (args.image,), file=sys.stderr)
        return 2
    print("image: %s (%dx%d)" % (args.image, gray.shape[1], gray.shape[0]))

    os.makedirs(args.out, exist_ok=True)
    boxes, score, prob = detect(gray, args.out, long_side=args.long)
    print("detector: %d boxes (score_map %s, max %.4f)" %
          (len(boxes), score.shape, float(score.max())))

    results = []
    for i, quad in enumerate(sort_boxes(boxes)):
        strip = crop_line(gray, quad)
        if strip.size == 0 or strip.shape[0] < 4 or strip.shape[1] < 4:
            continue
        text, conf = recognize(strip, args.out, i)
        text = lib.normalize_text(text)
        pts = np.asarray(quad).reshape(4, 2)
        results.append({"index": i, "text": text, "conf": conf,
                        "box": [round(float(v), 1) for v in pts.reshape(-1)]})
        print("  [%d] %-24r y=%.0f" % (i, text, pts[:, 1].mean()))

    print("--- recognised text ---")
    for r in results:
        print(r["text"])

    # Same key as the packaged entry point ocr.py, so one JSON schema serves
    # both the source tree and the standalone exe.
    with open(os.path.join(args.out, "result.json"), "w", encoding="utf-8") as fh:
        json.dump({"image": args.image, "lines": results}, fh,
                  ensure_ascii=False, indent=2)
    print("result written to %s" % os.path.join(args.out, "result.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
