#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify the slimmed build: drop unused model assets and re-run acceptance.

Copies the packaged build to a scratch directory, removes every asset the
pipeline never references, and confirms the full scene suite still passes.
The original build is never touched.
"""
import json
import os
import shutil
import subprocess
import sys

DIST = sys.argv[1] if len(sys.argv) > 1 else r"E:\ocr\build\ocr"
SCRATCH = os.path.abspath(os.path.join(os.path.dirname(DIST), "_slim_test"))
CASES = r"E:\ocr\ocr\test_images"
MIN_PATH = os.pathsep.join([r"C:\Windows\system32", r"C:\Windows"])

DROP = [
    "DeepSR_REPSR_R_M4C16_Flip_ep24.xnet",
    "FPMMFG1V1.2.0.26.xnet",
    "FPMMFG2V1.3.1.26.xnet",
    "paragraph_det_fp16_v2.xnet",
    "PrivacyDetectV8.0.26.xnet",
    "QBarDetV1.7.0.26.xnet",
    "QBarSegV1.1.0.26.xnet",
    "wxocr.dll",
    "x64.config",
    "file_component.xml",
    "sohu_simp.txt",
]


def norm(s):
    return "".join(ch for ch in s if not ch.isspace())


def main():
    if os.path.isdir(SCRATCH):
        shutil.rmtree(SCRATCH, ignore_errors=True)
    shutil.copytree(DIST, SCRATCH)
    model_dir = os.path.join(SCRATCH, "models", "WeChatOcr-8096")
    freed = 0
    for name in DROP:
        p = os.path.join(model_dir, name)
        if os.path.isfile(p):
            freed += os.path.getsize(p)
            os.remove(p)
    print("removed %d unused files, freed %.1f MB" % (len(DROP), freed / 1024 / 1024))

    with open(os.path.join(CASES, "manifest.json"), "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    env = dict(os.environ)
    env["PATH"] = MIN_PATH
    exe = os.path.join(SCRATCH, "ocr.exe")
    passed = 0
    fails = []
    for name, meta in manifest.items():
        out = os.path.join(SCRATCH, "_c", name)
        p = subprocess.run([exe, meta["path"], "--out", out],
                           capture_output=True, text=True, env=env,
                           errors="replace", timeout=900)
        lines = []
        rp = os.path.join(out, "result.json")
        if os.path.isfile(rp):
            with open(rp, "r", encoding="utf-8") as fh:
                lines = [l["text"] for l in json.load(fh).get("lines", [])]
        got = [norm(x) for x in lines]
        missing = [e for e in meta["expected"] if norm(e) not in got]
        if p.returncode == 0 and not missing:
            passed += 1
        else:
            fails.append((name, p.returncode, missing))
        print("%-14s %s" % (name, "PASS" if (p.returncode == 0 and not missing) else "FAIL"))

    # Measure the build size without the per-case output directories, which
    # the runs above created and which are not part of the deliverable.
    def build_size(root):
        total = 0
        for base, dirs, files in os.walk(root):
            if os.path.basename(base) in ("_c", "_case", "_out"):
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs if d not in ("_c", "_case", "_out")]
            for f in files:
                total += os.path.getsize(os.path.join(base, f))
        return total

    size = build_size(SCRATCH)
    print("slimmed build size: %.1f MB" % (size / 1024 / 1024))
    print("--- slimmed build: %d/%d passed ---" % (passed, len(manifest)))
    if fails:
        print("failures: %s" % fails)

    # The scratch copy is throwaway: it duplicates _internal and models, so
    # leaving it behind would double the build directory size.
    shutil.rmtree(SCRATCH, ignore_errors=True)
    print("removed scratch %s" % SCRATCH)
    return 0 if passed == len(manifest) else 1


if __name__ == "__main__":
    sys.exit(main())
