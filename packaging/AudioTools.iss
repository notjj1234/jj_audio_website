; Inno Setup script for Audio Tools (PyInstaller onedir).
; Compile after: pyinstaller packaging/audio_tools.spec
;   powershell -File packaging/make_windows_installer.ps1 -Flavor cpu
;   powershell -File packaging/make_windows_installer.ps1 -Flavor cuda
;
; Optional defines (ISCC /DName=Value):
;   DistDir    - folder containing AudioTools.exe (default: ..\dist\AudioTools)
;   OutputDir  - where Setup.exe is written (default: ..\dist)
;   AppVersion - version string (default: 0.1.3)
;   Flavor     - cpu (default) or cuda

#ifndef DistDir
  #define DistDir "..\dist\AudioTools"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif
#ifndef AppVersion
  #define AppVersion "0.1.3"
#endif
#ifndef Flavor
  #define Flavor "cpu"
#endif

#define MyAppExeName "AudioTools.exe"
#define MyAppPublisher "Audio Tools"
#define MyAppURL "https://github.com/notjj1234/jj_audio_website"
#define WebView2Url "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
; Evergreen WebView2 Runtime client id
#define WebView2ClientGuid "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

#if Flavor == "cuda"
  #define MyAppName "Audio Tools (NVIDIA)"
  #define MyAppFolder "AudioTools NVIDIA"
  #define MyAppId "{{C4E91A2B-7D83-4F16-9B50-2A8E6C3D1F47}"
  #define MyAppVerDesc "NVIDIA CUDA demo"
#else
  #define MyAppName "Audio Tools (CPU)"
  #define MyAppFolder "AudioTools"
  #define MyAppId "{{A7C3E8F1-4B2D-4E9A-9C1F-8D6B5A2E0F73}"
  #define MyAppVerDesc "CPU demo"
#endif

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppVerName={#MyAppName} {#AppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
VersionInfoVersion={#AppVersion}
VersionInfoProductVersion={#AppVersion}
VersionInfoProductName={#MyAppName}
VersionInfoDescription={#MyAppVerDesc}
DefaultDirName={autopf}\{#MyAppFolder}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=
OutputDir={#OutputDir}
OutputBaseFilename=AudioTools-{#AppVersion}-windows-x64-{#Flavor}-setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
; max shrinks the download; block threads keep compile time reasonable. LZMA2
; decompression speed is preset-independent, so a smaller payload also installs faster.
Compression=lzma2/max
LZMANumBlockThreads=4
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes
RestartApplications=no
; Large Torch/Demucs tree — show progress clearly
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Entire PyInstaller onedir (exe + _internal + ffmpeg + UI assets)
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
function WebView2Installed: Boolean;
var
  Version: String;
begin
  Result := False;
  if RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{#WebView2ClientGuid}', 'pv', Version) then
  begin
    if (Version <> '') and (Version <> '0.0.0.0') then
    begin
      Result := True;
      Exit;
    end;
  end;
  if RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{#WebView2ClientGuid}', 'pv', Version) then
  begin
    if (Version <> '') and (Version <> '0.0.0.0') then
    begin
      Result := True;
      Exit;
    end;
  end;
  if RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{#WebView2ClientGuid}', 'pv', Version) then
  begin
    if (Version <> '') and (Version <> '0.0.0.0') then
      Result := True;
  end;
end;

function SetupIsCuda: Boolean;
begin
  Result := CompareText('{#Flavor}', 'cuda') = 0;
end;

function NvidiaAdapterPresent: Boolean;
var
  Locator, Service, Adapters, Adapter: Variant;
  I: Integer;
  Name: String;
begin
  Result := False;
  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    Service := Locator.ConnectServer('', 'root\CIMV2');
    Adapters := Service.ExecQuery('SELECT Name FROM Win32_VideoController');
    if VarIsNull(Adapters) then
      Exit;
    for I := 0 to Adapters.Count - 1 do
    begin
      Adapter := Adapters.ItemIndex(I);
      Name := LowerCase(Adapter.Name);
      if Pos('nvidia', Name) > 0 then
      begin
        Result := True;
        Exit;
      end;
    end;
  except
  end;
end;

function InitializeSetup: Boolean;
var
  Answer: Integer;
  ErrorCode: Integer;
begin
  Result := True;
  if not WebView2Installed then
  begin
    Answer := MsgBox(
      'Microsoft Edge WebView2 Runtime was not detected.'#13#10#13#10 +
      'Audio Tools needs WebView2 for its window (included with Windows 11 and recent Windows 10).'#13#10#13#10 +
      'Open the WebView2 download page now? You can install Audio Tools anyway and add WebView2 later.',
      mbConfirmation, MB_YESNO);
    if Answer = IDYES then
      ShellExec('open', '{#WebView2Url}', '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
  end;
  if SetupIsCuda and (not NvidiaAdapterPresent) then
  begin
    MsgBox(
      'No NVIDIA graphics adapter was detected.'#13#10#13#10 +
      'This Setup is the NVIDIA CUDA edition. Isolation on GPU needs an NVIDIA card and current drivers.'#13#10#13#10 +
      'You can still install. Without NVIDIA hardware, Audio Isolation will run on CPU (same as the smaller CPU Setup).',
      mbInformation, MB_OK);
  end;
end;
