@echo off
echo Building IFC Extractor...
pyinstaller ifc_extractor.spec --clean
echo.
echo Done! Find your exe in the dist\ folder.
pause
