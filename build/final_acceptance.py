#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Final acceptance: source tree, packaged exe, and the isolated copy."""
import json
import os
import shutil
import subprocess
import sys

ROOT = r"E:\ocr"
CASES = os.path.join(ROOT, "ocr", "test_images")
DIST = os.path.join(ROOT, "build", "ocr")
DESK = r"C:\Users\90776\Desktop\ocr_final"
MIN_PATH = os.pathsep.join([r"C:\Windows\system32", r"C:\Windows",
                            r"C:\Windows\System32\Wbem"])


def norm(s):
    return "".join(ch for ch in s if not ch.isspace())


def run_case(exe, image, out, minimal, script=None):
    env = dict(os.environ)
    env["PATH"] = MIN_PATH if minimal else os.environ.get("PATH", "")
    # A Python interpreter needs the script path; a packaged exe does not.
    cmd = [exe] + ([script] if script else []) + [image, "--out", out]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env,
                          errors="replace", timeout=900)
    lines = []
    rp = os.path.join(out, "result.json")
    if os.path.isfile(rp):
        with open(rp, "r", encoding="utf-8") as fh:
            lines = [l["text"] for l in json.load(fh).get("lines", [])]
    return proc.returncode, [norm(x) for x in lines]


def score(label, exe, minimal, work, script=None):
    with open(os.path.join(CASES, "manifest.json"), "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    passed = 0
    fails = []
    for name, meta in manifest.items():
        out = os.path.join(work, name)
        code, got = run_case(exe, meta["path"], out, minimal, script)
        missing = [e for e in meta["expected"] if norm(e) not in got]
        if code == 0 and not missing:
            passed += 1
        else:
            fails.append((name, code, missing))
    print("%-34s %2d/%2d  %s" % (label, passed, len(manifest),
                                 "OK" if not fails else "FAIL %s" % fails))
    return passed == len(manifest)


def main():
    results = []
    # 1. source tree
    results.append(score("source tree (normal PATH)",
                         sys.executable, False,
                         os.path.join(ROOT, "ocr", "_final_src"),
                         script=os.path.join(ROOT, "ocr", "ocr.py")))
    # 2. packaged exe at build location
    results.append(score("packaged exe (normal PATH)",
                         os.path.join(DIST, "ocr.exe"), False,
                         os.path.join(DIST, "_final")))
    # 3. packaged exe copied elsewhere + minimal PATH (no Python, no Weixin)
    if os.path.isdir(DESK):
        shutil.rmtree(DESK, ignore_errors=True)
    shutil.copytree(DIST, DESK)
    results.append(score("copied exe + minimal PATH",
                         os.path.join(DESK, "ocr.exe"), True,
                         os.path.join(DESK, "_final")))

    print("--- %d/3 configurations passed ---" % sum(1 for r in results if r))

    # The per-case output directories are run residue, not deliverables, and
    # they more than double the build directory size.
    for leftover in (os.path.join(ROOT, "ocr", "_final_src"),
                     os.path.join(DIST, "_final")):
        shutil.rmtree(leftover, ignore_errors=True)
    shutil.rmtree(DESK, ignore_errors=True)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
