#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Close the dependency blind spots: delay-loaded imports and runtime loads.

objdump's import list omits delay-load entries, and LoadLibrary/LoadLibraryEx
resolve names at runtime. This scan reports both so the standalone claim does
not rest on a blind spot.
"""
import os
import re
import subprocess
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else r"E:\ocr\build\ocr"
OBJDUMP = r"C:\ProgramData\mingw64\mingw64\bin\objdump.exe"


def pe_files():
    for base, _d, files in os.walk(ROOT):
        for f in files:
            if f.lower().endswith((".exe", ".dll", ".pyd")):
                yield os.path.join(base, f)


def delay_imports(path):
    out = subprocess.run([OBJDUMP, "-p", path], capture_output=True,
                         text=True, errors="replace", timeout=120).stdout
    block = re.search(r"Delay Import[^\n]*\n(.*?)(?:\n\s*\n|\Z)", out, re.S)
    names = []
    if block:
        names = re.findall(r"\s([A-Za-z0-9_\-\.]+\.dll)", block.group(1), re.I)
    return [n for n in names if n.lower() != "user32.dll" or True]


def runtime_loads(path):
    with open(path, "rb") as fh:
        data = fh.read()
    ascii_data = data.decode("latin-1")
    loads = set()
    for m in re.finditer(r"LoadLibrary[EWAX]?", ascii_data):
        loads.add(m.group(0))
    # Literal DLL names that appear near a load call are the interesting ones.
    dlls = set(re.findall(r"[A-Za-z0-9_\-\.]{2,40}\.dll", ascii_data))
    return sorted(loads), sorted(dlls)


def main():
    pes = list(pe_files())
    print("scanning %d PE files for delay-load and runtime loads" % len(pes))

    total_delay = set()
    for pe in pes:
        for name in delay_imports(pe):
            total_delay.add(name.lower())
    print("\n--- delay-loaded DLLs (%d) ---" % len(total_delay))
    if total_delay:
        build = {f.lower() for _b, _d, fs in os.walk(ROOT) for f in fs}
        for n in sorted(total_delay):
            where = "bundled" if n in build else "system-or-external"
            print("  %-30s %s" % (n, where))
    else:
        print("  (none)")

    load_api = set()
    literal = set()
    for pe in pes:
        apis, dlls = runtime_loads(pe)
        load_api.update(apis)
        literal.update(dlls)
    print("\n--- runtime load APIs present ---")
    print("  " + (", ".join(sorted(load_api)) if load_api else "(none)"))
    print("\n--- literal .dll names referenced in binaries (top 25) ---")
    for n in sorted(literal)[:25]:
        print("  " + n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
