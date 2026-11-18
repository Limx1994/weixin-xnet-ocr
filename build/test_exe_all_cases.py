#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the packaged exe over every acceptance case under a minimal PATH."""
import json
import os
import subprocess
import sys

DIST = sys.argv[1] if len(sys.argv) > 1 else r"E:\ocr\build\ocr"
CASES = r"E:\ocr\ocr\test_images"
MINIMAL_PATH = os.pathsep.join([
    r"C:\Windows\system32", r"C:\Windows", r"C:\Windows\System32\Wbem",
])


def norm(s):
    return "".join(ch for ch in s if not ch.isspace())


def main():
    with open(os.path.join(CASES, "manifest.json"), "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    exe = os.path.join(DIST, "ocr.exe")
    env = dict(os.environ)
    env["PATH"] = MINIMAL_PATH

    passed = 0
    total = 0
    for name, meta in manifest.items():
        total += 1
        out = os.path.join(DIST, "_case", name)
        proc = subprocess.run([exe, meta["path"], "--out", out],
                              capture_output=True, text=True, env=env,
                              errors="replace", timeout=900)
        lines = []
        rp = os.path.join(out, "result.json")
        if os.path.isfile(rp):
            with open(rp, "r", encoding="utf-8") as fh:
                lines = [l["text"] for l in json.load(fh).get("lines", [])]
        got = [norm(x) for x in lines]
        missing = [e for e in meta["expected"] if norm(e) not in got]
        ok = proc.returncode == 0 and not missing
        passed += 1 if ok else 0
        print("%-14s %s  missing=%s" % (name, "PASS" if ok else "FAIL", missing))
    print("--- packaged exe: %d/%d passed (minimal PATH) ---" % (passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
