; Instalador do Chuva SP para Windows (Inno Setup 6)
; Gerado no GitHub Actions a partir de dist\ChuvaSP (PyInstaller).
#define NomeApp "Chuva SP"
#define VersaoApp "1.0"

[Setup]
AppId={{8C1F2E7A-3B5D-4C9E-9A11-5F2D6B7C8E90}
AppName={#NomeApp}
AppVersion={#VersaoApp}
AppVerName={#NomeApp} {#VersaoApp}
AppPublisher=Rafael Grecco Sanches
DefaultDirName={autopf}\Chuva SP
DefaultGroupName=Chuva SP
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist_instalador
OutputBaseFilename=ChuvaSP-Instalador
SetupIconFile=icone.ico
UninstallDisplayIcon={app}\ChuvaSP.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\ChuvaSP\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Chuva SP"; Filename: "{app}\ChuvaSP.exe"
Name: "{group}\Desinstalar o Chuva SP"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Chuva SP"; Filename: "{app}\ChuvaSP.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ChuvaSP.exe"; Description: "{cm:LaunchProgram,Chuva SP}"; Flags: nowait postinstall skipifsilent
