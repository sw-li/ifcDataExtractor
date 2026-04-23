# ifc_extractor.spec
# Build with:  pyinstaller ifc_extractor.spec --clean
#
# Before building:
#   - Make sure "IFC Extractor.exe" is NOT running (taskkill /f /im "IFC Extractor.exe")
#   - Run from a non-admin terminal

import sys
import os
import sysconfig
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

# ---------------------------------------------------------------------------
# Locate ifcopenshell manually — collect_all can fail when the package
# is installed as a compiled extension or in a non-standard layout.
# ---------------------------------------------------------------------------

def _find_package_dir(name):
    """Return the directory of an installed package, or None."""
    for path in sys.path:
        candidate = os.path.join(path, name)
        if os.path.isdir(candidate):
            return candidate
    return None

ifc_dir = _find_package_dir("ifcopenshell")

if ifc_dir:
    # Walk the entire ifcopenshell folder and include every file as data
    ifc_datas = []
    for root, dirs, files in os.walk(ifc_dir):
        dest = os.path.relpath(root, os.path.dirname(ifc_dir))
        for f in files:
            ifc_datas.append((os.path.join(root, f), dest))
    ifc_binaries = []
    print(f"[spec] Found ifcopenshell at: {ifc_dir} ({len(ifc_datas)} files collected)")
else:
    # Fall back to collect_all
    ifc_datas, ifc_binaries, _ = collect_all("ifcopenshell")
    print("[spec] ifcopenshell directory not found — using collect_all fallback")

# openpyxl has a built-in hook in _pyinstaller_hooks_contrib, so collect_all works fine
openpyxl_datas, openpyxl_binaries, openpyxl_hiddenimports = collect_all("openpyxl")

# customtkinter ships image assets that must be bundled as data
ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all("customtkinter")

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=ifc_binaries + openpyxl_binaries + ctk_binaries,
    datas=ifc_datas + openpyxl_datas + ctk_datas,
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
            # Common ifcopenshell internals that may not be auto-detected
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

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="IFC Extractor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,        # set True temporarily if you need to see crash errors
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=None,            # replace with "icon.ico" if you have one
)
