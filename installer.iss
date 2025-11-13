; Inno Setup script for Veo3
[Setup]
AppName=Veo3 Video Tool
AppVersion=1.0.0
DefaultDirName={pf}\Veo3
DefaultGroupName=Veo3
OutputDir=dist
OutputBaseFilename=Veo3Setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
DisableDirPage=no
DisableProgramGroupPage=no

[Files]
Source: "dist\Veo3App.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Veo3"; Filename: "{app}\Veo3App.exe"
Name: "{commondesktop}\Veo3"; Filename: "{app}\Veo3App.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
Filename: "{app}\Veo3App.exe"; Description: "Launch Veo3"; Flags: nowait postinstall skipifsilent


