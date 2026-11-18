#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve every external path the OCR pipeline depends on.

Nothing in the pipeline is tied to a fixed drive or install location: paths are
derived from this file's own location, and each can be overridden with an
environment variable. XNet.dll is located by searching the Weixin install
directory, so a different WeChat version or install path works without edits.

Environment overrides:
  XNET_MODEL_DIR   model + charset directory
  XNET_TOOLS_DIR   directory holding xnet_infer.exe
  XNET_WEIXIN_DIR  directory holding XNet.dll (auto-detected when unset)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _project_root():
    """Locate the directory that holds models\\, tools\\ and runtime\\.

    In a PyInstaller build the modules live inside the archive, so __file__
    points at a temporary extraction directory. In that case the install
    directory - the one holding the exe - is used instead, which keeps the
    bundled models and the inference driver next to the executable.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(HERE)


PROJECT_ROOT = _project_root()


def model_dir():
    override = os.environ.get("XNET_MODEL_DIR")
    if override:
        return override
    if getattr(sys, "frozen", False):
        # Packaged layout: <exe dir>\\models\\WeChatOcr-8096
        return os.path.join(_project_root(), "models", "WeChatOcr-8096")
    return os.path.join(PROJECT_ROOT, "models", "WeChatOcr-8096")


def tools_dir():
    override = os.environ.get("XNET_TOOLS_DIR")
    if override:
        return override
    if getattr(sys, "frozen", False):
        # The packaged layout keeps the driver next to the exe.
        return _project_root()
    return os.path.join(PROJECT_ROOT, "tools")


def infer_exe():
    override = os.environ.get("XNET_INFER")
    if override:
        return override
    return os.path.join(tools_dir(), "xnet_infer.exe")


def _weixin_candidates():
    """Yield plausible XNet.dll locations, bundled copy first.

    The bundled copy under <project>/runtime wins, so the project no longer
    depends on Weixin being installed. An explicit override always takes
    precedence over both.
    """
    override = os.environ.get("XNET_WEIXIN_DIR")
    if override:
        yield override
        return
    # The bundled copy wins in both modes, so neither the source tree nor the
    # packaged exe depends on a Weixin install.
    yield bundled_runtime_dir()
    if getattr(sys, "frozen", False):
        # Packaged layout also keeps a copy next to the exe.
        yield _project_root()
    roots = [
        os.environ.get("WEIXIN_ROOT"),
        r"C:\Program Files (x86)\Tencent\Weixin",
        r"C:\Program Files\Tencent\Weixin",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Tencent", "Weixin"),
    ]
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        # Prefer the newest version subdirectory when one exists.
        versions = []
        for name in os.listdir(root):
            sub = os.path.join(root, name)
            if os.path.isdir(sub) and name.count(".") >= 2:
                versions.append(sub)
        if versions:
            versions.sort(reverse=True)
            for v in versions:
                yield v
        yield root


def bundled_runtime_dir():
    """Directory holding the bundled XNet.dll copy."""
    if getattr(sys, "frozen", False):
        return _project_root()
    return os.path.join(PROJECT_ROOT, "runtime")


def weixin_dir():
    """Return the directory containing XNet.dll, or None when not found."""
    for cand in _weixin_candidates():
        if os.path.isfile(os.path.join(cand, "XNet.dll")):
            return cand
    return None


def require(name, path):
    """Raise a clear error when a required path is missing."""
    if not path or not os.path.exists(path):
        raise FileNotFoundError(
            "%s not found: %s\n"
            "Set the matching environment variable (XNET_MODEL_DIR, "
            "XNET_TOOLS_DIR, XNET_INFER or XNET_WEIXIN_DIR) or place the file "
            "at the path above." % (name, path))
    return path


def diagnose():
    """Return a human-readable report of every resolved path."""
    wx = weixin_dir()
    bundled = bundled_runtime_dir()
    src = "bundled" if wx == bundled else ("weixin" if wx else "none")
    lines = [
        ("model dir", model_dir(), os.path.isdir(model_dir())),
        ("infer exe", infer_exe(), os.path.isfile(infer_exe())),
        ("xnet dll", wx or "(not found)", wx is not None),
    ]
    for label, path, ok in lines:
        print("%-12s %s  %s%s" % (label, "OK " if ok else "MISS", path,
                                  "  [source: %s]" % src if label == "xnet dll" else ""))
    charset = os.path.join(model_dir(), "charset_zh13562.txt")
    print("%-12s %s  %s" % ("charset", "OK " if os.path.isfile(charset) else "MISS", charset))
    for name in ("text_det_fp16_v2.xnet", "text_rec_zh13562_fp16_v2.xnet"):
        p = os.path.join(model_dir(), name)
        print("%-12s %s  %s" % ("model", "OK " if os.path.isfile(p) else "MISS", p))
    return all(ok for _, _, ok in lines)


if __name__ == "__main__":
    import sys
    sys.exit(0 if diagnose() else 1)
