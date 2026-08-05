; Loadvia 1.1.1 Inno Setup Script
; Compatible with Inno Setup 6.x and 7.x

#define MyAppName "Loadvia"
#define MyAppVersion "1.1.1"
#define MyAppPublisher "Loadvia"
#define MyAppExeName "Loadvia.exe"

[Setup]
AppId={{6411DE40-247B-45E7-9345-73DCCAF9DA69}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName=Loadvia 1.1.1
AppPublisher=Loadvia
AppPublisherURL=https://github.com/zahidkaya1/KolayIndir
AppSupportURL=https://github.com/zahidkaya1/KolayIndir/issues
AppUpdatesURL=https://github.com/zahidkaya1/KolayIndir/releases

DefaultDirName={autopf}\Loadvia
DefaultGroupName=Loadvia

OutputDir=..\release
OutputBaseFilename=Loadvia-Setup-1.1.1

SetupIconFile=..\assets\Loadvia-Brand-Assets\loadvia.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

Compression=lzma2
SolidCompression=yes
WizardStyle=modern

VersionInfoVersion=1.1.1.1
VersionInfoProductVersion=1.1.1.1
VersionInfoProductName=Loadvia
VersionInfoDescription=Loadvia Kurulum Programı
VersionInfoCompany=Loadvia
VersionInfoCopyright=Copyright © 2026 Loadvia
VersionInfoOriginalFileName=Loadvia-Setup-1.1.1.exe

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UsePreviousPrivileges=yes
UsePreviousAppDir=yes

AllowNoIcons=yes
DisableProgramGroupPage=no

CloseApplications=yes
RestartApplications=no
RestartIfNeededByRun=no

Uninstallable=yes
CreateUninstallRegKey=yes

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\Loadvia\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
