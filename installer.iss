; installer.iss — Inno Setup script for IFC Extractor
;
; Prerequisites:
;   Install Inno Setup 6 from https://jrsoftware.org/isinfo.php
;   Then run build.bat (or compile this file directly in the Inno Setup IDE).
;
; What this produces:
;   installer\IFC_Extractor_Setup.exe
;
; What the installer does for end-users:
;   - Copies all app files to %ProgramFiles%\IFC Extractor\
;   - Creates a Start Menu shortcut
;   - Creates an optional Desktop shortcut
;   - Registers an uninstaller (visible in Windows "Apps & features")
;   - App opens instantly after install — no temp-dir unpacking on each launch

#define AppName      "IFC Extractor"
#define AppVersion   "1.0"
#define AppPublisher "Ingerop"
#define AppExeName   "IFC Extractor.exe"
#define SourceDir    "dist\IFC Extractor"

[Setup]
AppId={{A3F2C1D4-8B7E-4F9A-B2C5-1D3E6F8A0B4C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisherURL=https://www.ingerop.com
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=IFC_Extractor_Setup
Compression=lzma2/ultra64
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
SolidCompression=yes
WizardStyle=modern
; Require normal user rights — no admin needed to install to user AppData
; Change to admin if you want to install to Program Files for all users
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french";  MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Copy the entire PyInstaller output folder into the install directory
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu shortcut
Name: "{group}\{#AppName}";        Filename: "{app}\{#AppExeName}"
; Desktop shortcut (optional — shown as a task above)
Name: "{autodesktop}\{#AppName}";  Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
; Uninstall entry in Start Menu
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
