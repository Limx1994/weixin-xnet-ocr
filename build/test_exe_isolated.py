#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify the packaged exe runs with no Python and no Weixin on PATH.

This is the decisive portability test: the target machine is emulated by
reducing PATH to core Windows directories only.
"""
import os
import subprocess
import sys

DIST = sys.argv[1] if len(sys.argv) > 1 else r"E:\ocr\build\ocr"
IMAGE = sys.argv[2] if len(sys.argv) > 2 else r"E:\ocr\ocr\test_images\plain.png"

MINIMAL_PATH = os.pathsep.join([
    r"C:\Windows\system32",
    r"C:\Windows",
    r"C:\Windows\System32\Wbem",
])


def main():
    exe = os.path.join(DIST, "ocr.exe")
    if not os.path.isfile(exe):
        print("missing %s" % exe)
        return 1
    env = dict(os.environ)
    env["PATH"] = MINIMAL_PATH
    for key in ("XNET_WEIXIN_DIR", "XNET_MODEL_DIR", "XNET_TOOLS_DIR", "WEIXIN_ROOT"):
        env.pop(key, None)

    out = os.path.join(DIST, "_out")
    proc = subprocess.run([exe, IMAGE, "--out", out],
                          capture_output=True, text=True, env=env,
                          errors="replace", timeout=900)
    print("PATH = %s" % MINIMAL_PATH)
    print("exit=%d" % proc.returncode)
    if proc.stdout:
        print("--- stdout ---")
        print(proc.stdout.strip()[:600])
    if proc.returncode != 0:
        print("--- stderr ---")
        print(proc.stderr[-800:])
        return 1

    import json
    result = os.path.join(out, "result.json")
    if os.path.isfile(result):
        with open(result, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        print("--- result.json ---")
        for line in data.get("lines", []):
            print(repr(line["text"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
