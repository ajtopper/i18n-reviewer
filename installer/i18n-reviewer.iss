; Optional Inno Setup installer script for i18n Reviewer (Windows x64)
#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif

[Setup]
AppId={{7B6F5C4E-8F7A-4D8C-9F31-9E2E68F3C211}
AppName=i18n Reviewer
AppVersion={#MyAppVersion}
AppPublisher=i18n Reviewer Contributors
DefaultDirName={autopf}\i18n Reviewer
DefaultGroupName=i18n Reviewer
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=i18n-reviewer-{#MyAppVersion}-setup-win64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\i18n-reviewer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\i18n Reviewer"; Filename: "{app}\i18n-reviewer.exe"
Name: "{autodesktop}\i18n Reviewer"; Filename: "{app}\i18n-reviewer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\i18n-reviewer.exe"; Description: "{cm:LaunchProgram,i18n Reviewer}"; Flags: nowait postinstall skipifsilent

