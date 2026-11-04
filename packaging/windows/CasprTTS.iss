#ifndef AppVersion
  #error AppVersion must be supplied by build.ps1
#endif
#ifndef BundleDir
  #error BundleDir must be supplied by build.ps1
#endif
#ifndef OutputDir
  #error OutputDir must be supplied by build.ps1
#endif
#ifndef NumericVersion
  #define NumericVersion "0.0.0"
#endif
[Setup]
; Never change this ID: all versions upgrade the same per-user application.
AppId={{822F2899-F395-468E-A24E-D4105C734461}
AppName=Caspr TTS
AppVersion={#AppVersion}
VersionInfoVersion={#NumericVersion}
AppPublisher=JacquesJnr
AppPublisherURL=https://github.com/JacquesJnr/CasprTTS
DefaultDirName={localappdata}\Programs\Caspr TTS
DefaultGroupName=Caspr TTS
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir={#OutputDir}
OutputBaseFilename=Caspr-TTS-{#AppVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\CasprTTS.exe
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
#ifdef SignBuild
SignTool=release
SignedUninstaller=yes
#endif
[InstallDelete]
; Remove obsolete bundled libraries on upgrade, never the separate user data.
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\third-party"
[Tasks]
Name: "startup"; Description: "Start Caspr TTS when I sign in (runs in the notification area)"; Flags: unchecked
[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
#ifdef WebView2Bootstrapper
Source: "{#WebView2Bootstrapper}"; DestDir: "{tmp}"; Flags: deleteafterinstall
#endif
[Icons]
Name: "{group}\Caspr TTS"; Filename: "{app}\CasprTTS.exe"
Name: "{group}\Uninstall Caspr TTS"; Filename: "{uninstallexe}"
Name: "{userstartup}\Caspr TTS"; Filename: "{app}\CasprTTS.exe"; Parameters: "background"; Tasks: startup
[Run]
#ifdef WebView2Bootstrapper
; The UI renders in Microsoft Edge WebView2 (preinstalled on Windows 11 and updated Windows 10).
; Run without elevation, Microsoft's bootstrapper installs the runtime for this user.
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; \
  StatusMsg: "Installing Microsoft Edge WebView2 Runtime..."; Check: NeedsWebView2; Flags: waituntilterminated
#endif
Filename: "{app}\CasprTTS.exe"; Description: "Launch Caspr TTS"; Flags: nowait postinstall skipifsilent
; User config/models live at {localappdata}\Caspr TTS, outside {app}.
; Deliberately no [UninstallDelete] or installer model seeding.
[Code]
const WebView2Client = 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function HasWebView2(Root: Integer): Boolean;
var Version: String;
begin
  Result := RegQueryStringValue(Root, WebView2Client, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0');
end;

function NeedsWebView2: Boolean;
begin
  Result := not (HasWebView2(HKLM32) or HasWebView2(HKCU));
end;
