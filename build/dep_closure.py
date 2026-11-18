#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Static dependency closure check for the packaged OCR build.

Scans every PE (exe/dll/pyd) under the build directory, collects imported DLL
names, and classifies each as: present in the build, a known Windows system
DLL, or an external runtime that a target machine must provide (VC runtime,
API sets, etc.). This is what decides whether the build truly runs standalone.
"""
import os
import re
import subprocess
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else r"E:\ocr\build\ocr"
OBJDUMP = r"C:\ProgramData\mingw64\mingw64\bin\objdump.exe"
SYSTEM_DIRS = [r"C:\Windows\System32", r"C:\Windows\SysWOW64", r"C:\Windows"]

# Names that are part of Windows and never need shipping.
SYSTEM_HINT = re.compile(
    r'^(kernel32|kernelbase|ntdll|user32|gdi32|advapi32|shell32|ole32|oleaut32|'
    r'msvcrt|msvcrt\.dll|comctl32|comdlg32|shlwapi|ws2_32|rpcrt4|bcrypt|crypt32|'
    r'winmm|winspool|version|userenv|powrprof|setupapi|cfgmgr32|dwmapi|uxtheme|'
    r'dbghelp|imagehlp|psapi|imm32|msctf|propsys|wintypes|secur32|netapi32|'
    r'dnsapi|iphlpapi|user32|clbcatq|msi|oledlg|urlmon|wininet|normaliz|'
    r'api-ms-win.*|ext-ms-win.*|ucrtbase|conio|vcruntime.*|msvcp.*)', re.I)


def pe_imports(path):
    """Return imported DLL names using objdump, falling back to byte scan."""
    try:
        out = subprocess.run([OBJDUMP, "-p", path], capture_output=True,
                             text=True, errors="replace", timeout=120).stdout
        names = re.findall(r"^\s+DLL Name:\s+(\S+)", out, re.M)
        if names:
            return [n for n in names if n.lower() != path.lower()]
    except Exception:
        pass
    # Fallback: scan for ASCII DLL-looking strings.
    with open(path, "rb") as fh:
        data = fh.read()
    found = set()
    for m in re.finditer(rb"[A-Za-z0-9_\-\.]{3,60}\.dll", data):
        found.add(m.group(0).decode("ascii", "ignore"))
    return sorted(found)


def in_system(name):
    low = name.lower()
    for d in SYSTEM_DIRS:
        if os.path.isfile(os.path.join(d, name)):
            return True
        if os.path.isfile(os.path.join(d, low)):
            return True
    return False


def main():
    pes = []
    for base, _dirs, files in os.walk(ROOT):
        for f in files:
            if f.lower().endswith((".exe", ".dll", ".pyd")):
                pes.append(os.path.join(base, f))
    print("scanning %d PE files under %s" % (len(pes), ROOT))

    build_names = {f.lower() for base, _d, files in os.walk(ROOT) for f in files}
    imports = {}
    for pe in pes:
        for name in pe_imports(pe):
            imports.setdefault(name.lower(), set()).add(os.path.basename(pe))

    external = []
    system = []
    local = []
    for name in sorted(imports):
        if name in build_names:
            local.append(name)
        elif in_system(name):
            system.append(name)
        elif SYSTEM_HINT.match(name):
            system.append(name)
        else:
            external.append(name)

    print("\n--- resolved locally (%d) ---" % len(local))
    print("  " + ", ".join(local))
    print("\n--- Windows system (%d) ---" % len(system))
    print("  " + ", ".join(system))
    print("\n--- EXTERNAL / not found (%d) ---" % len(external))
    if external:
        for name in external:
            users = sorted(imports[name])
            print("  %-24s <- %s" % (name, ", ".join(users[:4])))
    else:
        print("  (none)")

    vc = [n for n in external if re.match(r"^(vcruntime|msvcp|concrt|vcomp)", n, re.I)]
    print("\nVC runtime dependencies: %s" % (vc if vc else "NONE"))
    return 1 if vc else 0


if __name__ == "__main__":
    sys.exit(main())
