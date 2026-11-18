#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Decode a recogniser output directory and report the recognised text.

usage: python decode_rec.py <out_dir> [expected_text]
"""
import sys
import os
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xnet_ocr_lib as lib


def main():
    if len(sys.argv) < 2:
        print("usage: decode_rec.py <out_dir> [expected_text]")
        return 2
    out_dir = sys.argv[1]
    expected = sys.argv[2] if len(sys.argv) > 2 else None

    charset = lib.load_charset()
    print("charset size: %d" % len(charset))

    meta_path = os.path.join(out_dir, "output.json")
    if not os.path.exists(meta_path):
        print("missing %s" % meta_path)
        return 3
    with open(meta_path, "r", encoding="utf-8") as fh:
        meta = json.load(fh)
    dims = meta["dims"]
    kind = meta["kind"]
    count = int(np.prod(dims))
    print("output dims=%s kind=%d count=%d" % (dims, kind, count))

    arr = lib.read_output_bin(os.path.join(out_dir, "output.bin"), count)
    arr = arr.reshape(dims)

    logits = arr[0] if arr.ndim == 3 else arr
    probs = lib.softmax_rows(logits)
    text, conf = lib.ctc_decode(probs, charset)
    print("decoded: %r" % text)
    if conf:
        print("confidence: min=%.4f mean=%.4f max=%.4f" %
              (min(conf), sum(conf) / len(conf), max(conf)))
    if expected is not None:
        ok = (text == expected)
        print("expected: %r  match=%s" % (expected, ok))
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
