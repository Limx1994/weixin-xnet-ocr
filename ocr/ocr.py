#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Command-line entry point for WeChat XNet OCR.

usage:
  python ocr.py <image> [--long N] [--out DIR] [--json]

Prints one recognised line per text region, top-to-bottom.
"""
import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocr_image


def main():
    ap = argparse.ArgumentParser(description="WeChat XNet OCR")
    ap.add_argument("image", help="input image (PNG/JPEG/BMP)")
    ap.add_argument("--long", type=int, default=960,
                    help="detector long-side limit (default 960)")
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "_ocr_out"),
        help="working/output directory")
    ap.add_argument("--json", action="store_true",
                    help="emit the structured result as JSON only")
    args, _ = ap.parse_known_args()

    import numpy as np
    from PIL import Image
    os.makedirs(args.out, exist_ok=True)

    if not os.path.exists(args.image):
        print("error: image not found: %s" % args.image, file=sys.stderr)
        return 2
    try:
        img = Image.open(args.image).convert("L")
    except Exception as exc:
        print("error: cannot read image %s: %s" % (args.image, exc), file=sys.stderr)
        return 2
    gray = np.asarray(img, dtype=np.uint8)
    if gray.size == 0 or gray.shape[0] < 4 or gray.shape[1] < 4:
        print("error: image too small: %s" % (args.image,), file=sys.stderr)
        return 2

    boxes, score, prob = ocr_image.detect(gray, args.out, long_side=args.long)
    results = []
    for i, quad in enumerate(ocr_image.sort_boxes(boxes)):
        strip = ocr_image.crop_line(gray, quad)
        if strip.size == 0 or strip.shape[0] < 4 or strip.shape[1] < 4:
            continue
        text, conf = ocr_image.recognize(strip, args.out, i)
        import xnet_ocr_lib as lib
        text = lib.normalize_text(text)
        pts = np.asarray(quad).reshape(4, 2)
        results.append({"text": text, "conf": round(conf, 6),
                        "box": [round(float(v), 1) for v in pts.reshape(-1)]})

    payload = {"image": os.path.abspath(args.image), "lines": results}
    with open(os.path.join(args.out, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for r in results:
            print(r["text"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
