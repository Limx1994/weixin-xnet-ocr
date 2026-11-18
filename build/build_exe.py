#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a standalone OCR executable with PyInstaller.

The result is a directory build (build\\ocr_exe\\) containing:
  ocr.exe            the packaged entry point (no Python required on the target)
  xnet_infer.exe     the C++ inference driver
  runtime\\XNet.dll   the inference engine, bundled
  models\\            the .xnet models and the character set
  run_ocr_exe.bat    one-click launcher

Run this script from the project root:
    python build\\build_exe.py
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
OCR_DIR = os.path.join(PROJECT_ROOT, "ocr")
DIST_ROOT = os.path.join(PROJECT_ROOT, "build")
# PyInstaller names the output directory after --name, so this is build\\ocr.
DIST = os.path.join(DIST_ROOT, "ocr")
ENTRY = os.path.join(OCR_DIR, "ocr.py")


def run(cmd):
    print("$ " + " ".join(cmd))
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if proc.returncode != 0:
        raise SystemExit("command failed (%d): %s" % (proc.returncode, " ".join(cmd)))


def clean():
    for name in (DIST, os.path.join(DIST_ROOT, "build_tmp")):
        if os.path.isdir(name):
            shutil.rmtree(name, ignore_errors=True)
            print("removed %s" % name)


def build():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onedir", "--name", "ocr",
        "--distpath", DIST_ROOT,
        "--workpath", os.path.join(DIST_ROOT, "build_tmp"),
        "--specpath", os.path.join(DIST_ROOT, "spec"),
        "--hidden-import", "PIL._imaging",
        "--hidden-import", "numpy",
        ENTRY,
    ]
    run(cmd)
    print("packaged -> %s" % DIST)


def stage():
    """Copy the runtime pieces next to the packaged exe."""
    targets = {
        "xnet_infer.exe": os.path.join(PROJECT_ROOT, "tools", "xnet_infer.exe"),
        "XNet.dll": os.path.join(PROJECT_ROOT, "runtime", "XNet.dll"),
    }
    for name, src in targets.items():
        if not os.path.isfile(src):
            raise SystemExit("missing %s" % src)
        shutil.copy2(src, os.path.join(DIST, name))
        print("staged %s" % name)

    models_src = os.path.join(PROJECT_ROOT, "models", "WeChatOcr-8096")
    models_dst = os.path.join(DIST, "models", "WeChatOcr-8096")
    if os.path.isdir(models_dst):
        shutil.rmtree(models_dst, ignore_errors=True)
    shutil.copytree(models_src, models_dst)
    print("staged models -> %s" % models_dst)

    bat = os.path.join(DIST, "run_ocr_exe.bat")
    with open(bat, "w", encoding="ascii", newline="\r\n") as fh:
        fh.write(
            "@echo off\r\n"
            "REM One-click OCR. No Python installation required.\r\n"
            "REM Usage: run_ocr_exe.bat <image> [long_side]\r\n"
            "setlocal\r\n"
            "set \"HERE=%~dp0\"\r\n"
            "if \"%~1\"==\"\" goto :usage\r\n"
            "if \"%~2\"==\"\" (\r\n"
            "    \"%HERE%ocr.exe\" \"%~1\" --out \"%HERE%_out\"\r\n"
            ") else (\r\n"
            "    \"%HERE%ocr.exe\" \"%~1\" --long %~2 --out \"%HERE%_out\"\r\n"
            ")\r\n"
            "exit /b %ERRORLEVEL%\r\n\n"
            ":usage\r\n"
            "echo usage: run_ocr_exe.bat ^<image^> [long_side]\r\n"
            "echo example: run_ocr_exe.bat \"C:\\path\\to\\image.png\"\r\n"
            "exit /b 2\r\n")
    print("wrote %s" % bat)


UNUSED_ASSETS = [
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


def slim(models_dst):
    """Drop model assets the pipeline never references (saves ~40 MB).

    Only the detector, the recogniser and the character set are used; the rest
    of the shipped WeChatOcr bundle (super-resolution, face/privacy, QR, the
    OCR service plugin) is dead weight for this project. Verified by
    build\\test_slim.py: the full scene suite still passes afterwards.
    """
    freed = 0
    for name in UNUSED_ASSETS:
        p = os.path.join(models_dst, name)
        if os.path.isfile(p):
            freed += os.path.getsize(p)
            os.remove(p)
    print("slimmed: removed %d unused assets, freed %.1f MB"
          % (len(UNUSED_ASSETS), freed / 1024 / 1024))


def main():
    os.makedirs(DIST_ROOT, exist_ok=True)
    clean()
    build()
    stage()
    if "--slim" in sys.argv:
        slim(os.path.join(DIST, "models", "WeChatOcr-8096"))
    # PyInstaller's intermediate work directory is ~19 MB and is not needed
    # once the build succeeds.
    for tmp in (os.path.join(DIST_ROOT, "build_tmp"),
                os.path.join(DIST_ROOT, "spec")):
        shutil.rmtree(tmp, ignore_errors=True)
    print("done: %s" % DIST)
    return 0


if __name__ == "__main__":
    sys.exit(main())
