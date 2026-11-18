# Generates raw NCHW input files for XNet inference from text lines.
# usage: python make_input.py <text> <out.bin> [target_h] [mode] [mean] [std]
#   mode: gray (C=1) or rgb (C=3)
import sys
import os
import json
import struct
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xnet_ocr_lib as lib


def write_input_nchw(arr, out_path):
    """Write NCHW float32 with a header: rank(u64) + dims(rank*u64) + payload."""
    arr = np.ascontiguousarray(arr, dtype=np.float32)
    n, c, h, w = arr.shape
    with open(out_path, "wb") as fh:
        fh.write(struct.pack("<Q", 4))
        fh.write(struct.pack("<4q", int(n), int(c), int(h), int(w)))
        fh.write(arr.tobytes())
    meta = {"shape": [int(n), int(c), int(h), int(w)], "dtype": "float32"}
    with open(out_path + ".json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    return meta


def main():
    if len(sys.argv) < 3:
        print("usage: make_input.py <text> <out.bin> [target_h] [mode] [mean] [std]")
        return 2
    text = sys.argv[1]
    out = sys.argv[2]
    target_h = int(sys.argv[3]) if len(sys.argv) > 3 else 32
    mode = sys.argv[4] if len(sys.argv) > 4 else "gray"
    mean = float(sys.argv[5]) if len(sys.argv) > 5 else 0.5
    std = float(sys.argv[6]) if len(sys.argv) > 6 else 0.5

    gray = lib.render_line(text, height=64)
    if mode == "rgb":
        rgb = np.stack([gray, gray, gray], axis=2)
        arr = lib.preprocess_bgr(rgb, target_h=target_h,
                                 mean=(mean, mean, mean), std=(std, std, std))
    else:
        arr = lib.preprocess_gray(gray, target_h=target_h, mean=mean, std=std)
    meta = write_input_nchw(arr, out)
    print(json.dumps(meta))
    return 0


if __name__ == "__main__":
    sys.exit(main())
