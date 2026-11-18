#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Confirm the packaged exe loads its bundled VC runtime DLLs.

Uses PowerShell Get-Process -Module, which reports loaded modules without the
sampling race of tasklist.
"""
import json
import os
import subprocess
import sys

DIST = sys.argv[1] if len(sys.argv) > 1 else r"E:\ocr\build\ocr"
IMG = r"E:\ocr\ocr\test_images\plain.png"
PS = (
    "$p = Start-Process -FilePath '{exe}' -ArgumentList '{img}','--out','{out}' "
    "-PassThru -RedirectStandardOutput NUL -RedirectStandardError NUL; "
    "Start-Sleep -Seconds 3; "
    "$p | Select-Object -ExpandProperty Modules | "
    "Select-Object -ExpandProperty ModuleName | "
    "ConvertTo-Json"
)


def main():
    out = os.path.join(DIST, "_vccheck")
    cmd = PS.format(exe=os.path.join(DIST, "ocr.exe"), img=IMG, out=out)
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([r"C:\Windows\system32", r"C:\Windows"])
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                          capture_output=True, text=True, env=env,
                          errors="replace", timeout=900)
    if proc.returncode != 0:
        print("probe failed:", proc.stderr[-300:])
        return 1
    try:
        names = json.loads(proc.stdout or "[]")
    except Exception:
        print("parse failed:", proc.stdout[:300])
        return 1
    if isinstance(names, str):
        names = [names]
    vc = sorted({n for n in names if "vcruntime" in n.lower() or "msvcp" in n.lower()})
    print("modules reported: %d" % len(names))
    print("VC runtime loaded by ocr.exe: %s" % (vc if vc else "none"))
    bundled = os.path.join(DIST, "_internal")
    for f in ("VCRUNTIME140.dll", "VCRUNTIME140_1.dll"):
        print("%-20s present=%s" % (f, os.path.isfile(os.path.join(bundled, f))))
    return 0 if vc else 1


if __name__ == "__main__":
    sys.exit(main())
