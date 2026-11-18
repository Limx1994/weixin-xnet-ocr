#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Acceptance suite: run OCR over every generated case and score the result.

A case passes when every expected line is found among the recognised lines
after normalisation (whitespace-insensitive), in any order.
"""
import sys
import os
import json
import subprocess
import argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
WEIXIN_DIR = paths.weixin_dir() or ""

HERE = os.path.dirname(os.path.abspath(__file__))
CASES_DIR = os.path.join(HERE, "test_images")


def norm(s):
    return "".join(ch for ch in s if not ch.isspace())


def run_case(name, path, long_side, work_root):
    out_dir = os.path.join(work_root, name)
    env = dict(os.environ)
    env["PATH"] = WEIXIN_DIR + os.pathsep + env.get("PATH", "")
    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "ocr_image.py"), path,
         "--long", str(long_side), "--out", out_dir],
        capture_output=True, text=True, env=env, errors="replace", timeout=1800)
    result_path = os.path.join(out_dir, "result.json")
    lines = []
    if os.path.exists(result_path):
        with open(result_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        lines = [r["text"] for r in data.get("lines", [])]
    return proc.returncode, lines, proc.stdout + proc.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--long", type=int, default=960)
    ap.add_argument("--cases", default="")
    ap.add_argument("--work", default=os.path.join(HERE, "_accept"))
    args = ap.parse_args()

    with open(os.path.join(CASES_DIR, "manifest.json"), "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    names = args.cases.split(",") if args.cases else list(manifest.keys())

    passed = 0
    detail = []
    for name in names:
        if name not in manifest:
            print("skip unknown case %s" % name)
            continue
        expected = manifest[name]["expected"]
        code, lines, log = run_case(name, manifest[name]["path"], args.long, args.work)
        if code != 0:
            print("%-14s ERROR exit=%d" % (name, code))
            print("    " + log.strip().splitlines()[-1][:120] if log.strip() else "")
            detail.append((name, False, "exit %d" % code, expected, lines))
            continue
        got = [norm(x) for x in lines]
        missing = [e for e in expected if norm(e) not in got]
        ok = not missing
        passed += 1 if ok else 0
        print("%-14s %s  boxes=%d expected=%d missing=%s" %
              (name, "PASS" if ok else "FAIL", len(lines), len(expected), missing))
        for ln in lines:
            print("      | %s" % ln)
        detail.append((name, ok, "missing=%s" % missing, expected, lines))

    total = len(detail)
    print("--- summary: %d/%d passed ---" % (passed, total))
    with open(os.path.join(args.work, "acceptance.json"), "w", encoding="utf-8") as fh:
        json.dump({"long": args.long, "passed": passed, "total": total,
                   "detail": [{"case": n, "ok": o, "note": note,
                               "expected": e, "got": g} for n, o, note, e, g in detail]},
                  fh, ensure_ascii=False, indent=2)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
