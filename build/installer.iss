; ShapeYourPhoto Windows installer (Inno Setup 6)
; 用法: iscc build\installer.iss /DAppVersion=1.1.6
; CI 中由 GitHub Actions 注入 AppVersion；本地测试若不传，回退到 0.0.0
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "ShapeYourPhoto"
#define AppPublisher "Helloalp"
#define AppExeName "ShapeYourPhoto.exe"
; 固定 GUID，未来升级安装会覆盖同一应用，不要改
#define AppId "{{C8B1A5E0-7A2D-4F3E-9F0B-2E1D6A4C8B7F}"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
OutputDir=..\dist_installer
; 命名约定：ShapeYourPhoto-<version>-Windows-x64-Setup.exe
OutputBaseFilename=ShapeYourPhoto-{#AppVersion}-Windows-x64-Setup
SetupIconFile=..\assets\app_icon.ico
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName} {#AppVersion}
VersionInfoVersion={#AppVersion}.0
VersionInfoCompany={#AppPublisher}
VersionInfoProductName={#AppName}

[Languages]
; Inno Setup 自带的语言包仅有 Default.isl (English)。
; ChineseSimplified.isl 需手动下载放入 Languages/ 才有；CI 上 chocolatey 装的版本没有，
; 这里仅声明 English 避免 CI 编译失败。安装向导语言不影响 app 内中文 UI。
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; PyInstaller 输出目录直接拷入 {app}
Source: "..\dist\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

; 故意不在 [UninstallDelete] 删 {userappdata}\Helloalp\ShapeYourPhoto
; 卸载保留用户的 app_settings.json / usage_stats.json
