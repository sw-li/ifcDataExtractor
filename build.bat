@echo off
:: ============================================================
:: build.bat — IFC Extractor full build script
::
:: Step 1: PyInstaller  → dist\IFC Extractor\  (one-folder build)
:: Step 2: Inno Setup   → installer\IFC_Extractor_Setup.exe
::
:: Requirements:
::   - Run from a NON-ADMIN terminal  (PyInstaller will warn otherwise)
::   - Inno Setup 6 installed at the default path, OR iscc.exe on your PATH
::   - App must not be running: taskkill /f /im "IFC Extractor.exe"
:: ============================================================

echo.
echo ======================================================
echo  Step 1 — PyInstaller (one-folder build)
echo ======================================================
pyinstaller ifc_extractor.spec --clean
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller failed. Fix errors above before continuing.
    pause
    exit /b 1
)

echo.
echo ======================================================
echo  Step 2 — Inno Setup (create installer)
echo ======================================================

:: Try the default Inno Setup install location first, then fall back to PATH
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\iscc.exe"
if not exist %ISCC% set ISCC="%ProgramFiles%\Inno Setup 6\iscc.exe"
if not exist %ISCC% set ISCC=iscc.exe

%ISCC% installer.iss
if errorlevel 1 (
    echo.
    echo [WARNING] Inno Setup not found or failed.
    echo           Install Inno Setup 6 from https://jrsoftware.org/isinfo.php
    echo           The PyInstaller folder is still at dist\IFC Extractor\
    echo           and can be distributed manually in the meantime.
) else (
    echo.
    echo ======================================================
    echo  Done!
    echo  Installer: installer\IFC_Extractor_Setup.exe
    echo ======================================================
)

echo.
pause
