#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify the project runs with every Weixin path removed from the environment.

This is the strongest available portability test: the bundled runtime\\XNet.dll
must satisfy the whole pipeline, and no Weixin install may be required.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IMAGE = os.path.join(HERE, "test_images", "plain.png")
OUT = os.path.join(HERE, "_isolated_out")


def main():
    env = dict(os.environ)
    kept = [p for p in env.get("PATH", "").split(os.pathsep)
            if "Tencent" not in p and "Weixin" not in p]
    env["PATH"] = os.pathsep.join(kept)
    env.pop("XNET_WEIXIN_DIR", None)
    env.pop("WEIXIN_ROOT", None)
    print("PATH entries kept: %d (Tencent/Weixin removed)" % len(kept))

    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "ocr.py"), IMAGE, "--out", OUT],
        capture_output=True, text=True, env=env, errors="replace", timeout=600)
    print("exit=%d" % proc.returncode)
    print(proc.stdout.strip())
    if proc.returncode != 0:
        print("stderr:", proc.stderr[-400:])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
