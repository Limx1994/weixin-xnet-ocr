#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Static check: report undefined top-level names in the project scripts.

Catches migration mistakes (e.g. a constant renamed to a paths.* call while a
reference still uses the old bare name) without executing the scripts.
"""
import ast
import io
import os
import sys

ROOT = r"E:\ocr\ocr"

# Names commonly provided by imports or builtins; anything else unresolved is
# reported.
IMPORT_WHITELIST = {
    "os", "sys", "re", "io", "json", "glob", "time", "math", "random",
    "argparse", "subprocess", "struct", "shutil", "numpy", "np", "Image",
    "ImageDraw", "ImageFont", "ImageFilter", "pathlib", "path",
}


def defined_names(tree):
    names = set(dir(__builtins__)) | IMPORT_WHITELIST | {
        "__file__", "__name__", "__doc__", "__builtins__", "__spec__",
        "__package__", "__loader__", "__cached__", "__annotations__",
    }
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Param)):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Import):
            for a in node.names:
                names.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                names.add(a.asname or a.name)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, (ast.For, ast.AsyncFor)) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.withitem) and node.optional_vars:
            if isinstance(node.optional_vars, ast.Name):
                names.add(node.optional_vars.id)
        elif isinstance(node, ast.comprehension) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Global):
            names.update(node.names)
    return names


def main():
    bad = 0
    for fname in sorted(os.listdir(ROOT)):
        if not fname.endswith(".py"):
            continue
        path = os.path.join(ROOT, fname)
        with io.open(path, "r", encoding="utf-8") as fh:
            src = fh.read()
        try:
            tree = ast.parse(src)
        except SyntaxError as exc:
            print("%-24s SYNTAX %s" % (fname, exc))
            bad += 1
            continue
        known = defined_names(tree)
        # Attribute roots like paths.infer_exe() resolve through `import paths`,
        # which is already in IMPORT_WHITELIST handling above.
        used = {n.id for n in ast.walk(tree)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        missing = sorted(used - known)
        if missing:
            print("%-24s UNDEFINED: %s" % (fname, ", ".join(missing)))
            bad += 1
    print("--- %d file(s) with issues ---" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
