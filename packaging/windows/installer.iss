; Inno Setup script for Android Backup Manager.
;
; Consumes the PyInstaller output in dist\android-backup-manager and produces
; a single Setup .exe. Build with:
;
;     iscc /DAppVersion=1.2.3 packaging\windows\installer.iss
;
; NOTE ON SMARTSCREEN: this installer is unsigned. Windows will show
; "Windows protected your PC" until an OV/EV code-signing certificate is
; bought and applied. That is a purchasing decision, not a build one --
; the download page must tell users what they will see. See docs.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "Android Backup Manager"
#define AppPublisher "Ankit Srivastava"
#define AppExeName "android-backup-manager.exe"
#define AppURL "https://github.com/thisisankit27/android-backup-manager"

[Setup]
AppId={{7A3D1E64-9C42-4F1B-B0A6-2E5C8D9F3A11}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
; Per-user install by default: no UAC prompt, and this tool only ever
; touches the current user's phone and their own Desktop.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\installer-output
OutputBaseFilename=AndroidBackupManager-{#AppVersion}-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
DisableProgramGroupPage=yes
; Shown only if the repo actually has a LICENSE. Naming a missing file here
; is a hard ISCC compile error, which would fail the Windows release build.
#if FileExists(AddBackslash(SourcePath) + "..\..\LICENSE")
LicenseFile=..\..\LICENSE
#endif
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
; The whole PyInstaller output directory, preserving its layout.
Source: "..\..\dist\android-backup-manager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; PyInstaller unpacks to a temp dir at runtime; nothing else to clean.
Type: dirifempty; Name: "{app}"
