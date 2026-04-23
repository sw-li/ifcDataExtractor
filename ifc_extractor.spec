# ifc_extractor.spec  —  ONE-FOLDER build (used by the installer workflow)
#
# Build with:  pyinstaller ifc_extractor.spec --clean
#
# This produces dist\IFC Extractor\ (a folder, not a single exe).
# The installer script (installer.iss) then wraps that folder into a proper
# Windows setup wizard.
#
# Why one-folder instead of one-file?
#   One-file unpacks itself to a temp directory on every launch, causing a
#   10-20 s delay before the window appears.  One-folder installs the files
#   permanently to Program Files so the app opens instantly every time.
#
# Before building:
#   - Make sure "IFC Extractor.exe" is NOT running (taskkill /f /im "IFC Extractor.exe")
#   - Run from a non-admin terminal

import sys
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

# ---------------------------------------------------------------------------
# Locate packages manually — collect_all can fail when a package is installed
# as a compiled extension or in a non-standard layout.
# ---------------------------------------------------------------------------

def _find_package_dir(name):
    """Return the directory of an installed package, or None."""
    for path in sys.path:
        candidate = os.path.join(path, name)
        if os.path.isdir(candidate):
            return candidate
    return None


def _walk_package(pkg_dir):
    """Walk a package directory and return (src, dest) pairs for all files."""
    datas = []
    for root, dirs, files in os.walk(pkg_dir):
        dest = os.path.relpath(root, os.path.dirname(pkg_dir))
        for f in files:
            datas.append((os.path.join(root, f), dest))
    return datas


# ── ifcopenshell ─────────────────────────────────────────────────────────────
ifc_dir = _find_package_dir("ifcopenshell")
if ifc_dir:
    ifc_datas    = _walk_package(ifc_dir)
    ifc_binaries = []
    print(f"[spec] ifcopenshell: {ifc_dir} ({len(ifc_datas)} files)")
else:
    ifc_datas, ifc_binaries, _ = collect_all("ifcopenshell")
    print("[spec] ifcopenshell: collect_all fallback")

# ── openpyxl ─────────────────────────────────────────────────────────────────
openpyxl_datas, openpyxl_binaries, openpyxl_hiddenimports = collect_all("openpyxl")

# ── customtkinter ─────────────────────────────────────────────────────────────
ctk_dir = _find_package_dir("customtkinter")
if ctk_dir:
    ctk_datas    = _walk_package(ctk_dir)
    ctk_binaries = []
    print(f"[spec] customtkinter: {ctk_dir} ({len(ctk_datas)} files)")
else:
    ctk_datas, ctk_binaries, _ = collect_all("customtkinter")
    print("[spec] customtkinter: collect_all fallback")
ctk_hiddenimports = collect_submodules("customtkinter")

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=ifc_binaries + openpyxl_binaries + ctk_binaries,
    datas=ifc_datas + openpyxl_datas + ctk_datas + [("icon.ico", ".")],
    hiddenimports=(
        collect_submodules("ifcopenshell")
        + openpyxl_hiddenimports
        + collect_submodules("openpyxl")
        + ctk_hiddenimports
        + collect_submodules("customtkinter")
        + [
            "extractor.metadata",
            "extractor.hierarchy",
            "extractor.psets",
            "extractor.quantities",
            "filter",
            "exporter",
            "ui.app",
            "ifcopenshell.util",
            "ifcopenshell.util.element",
            "ifcopenshell.util.unit",
            "ifcopenshell.util.placement",
            "ifcopenshell.geom",
        ]
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

# ---------------------------------------------------------------------------
# EXE  — note: binaries and datas are NOT embedded here (they go into COLLECT)
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    [],                         # binaries go into COLLECT, not EXE
    exclude_binaries=True,      # required for one-folder mode
    name="IFC Extractor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,              # set True temporarily to see crash errors
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon="icon.ico",
)

# ---------------------------------------------------------------------------
# COLLECT  — assembles the final dist\IFC Extractor\ folder
# -------------------------------------------------------------------------