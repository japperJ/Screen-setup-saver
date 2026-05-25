#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

#ifndef AppExePath
  #define AppExePath "..\dist\app\ScreenSetupSaver.exe"
#endif

#define AppName "Screen Setup Saver"
#define AppExeName "ScreenSetupSaver.exe"

[Setup]
AppId={{6B9D5687-09D3-4FF0-83D2-D6B2E7EA5A3E}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
OutputDir=..\dist\installer
OutputBaseFilename=ScreenSetupSaver-Setup-{#AppVersion}

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
Name: "autostart"; Description: "Start Screen Setup Saver when I sign in"; Flags: unchecked

[Files]
Source: "{#AppExePath}"; DestDir: "{app}"; DestName: "{#AppExeName}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
Filename: "{sys}\schtasks.exe"; Parameters: "/Create /F /SC ONLOGON /TN ""ScreenSetupSaver"" /TR ""{app}\{#AppExeName}"""; Tasks: autostart; Flags: runhidden

[UninstallRun]
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /F /TN ""ScreenSetupSaver"""; Flags: runhidden
