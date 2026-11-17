[Setup]
AppId=ClaudeThinkingTranslation
AppName=Claude Thinking Translation
AppVersion={#Version}
AppPublisher=Claude Thinking Translation contributors
DefaultDirName={localappdata}\Programs\ClaudeThinkingTranslation
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputBaseFilename=Claude-Thinking-Translation-Windows-x64-Setup
Compression=lzma2
SolidCompression=yes
SetupLogging=yes

[Files]
Source: "payload\NOTICES.md"; DestDir: "{app}"
Source: "payload\*"; DestDir: "{tmp}\payload"; Flags: recursesubdirs createallsubdirs deleteafterinstall

[Run]
Filename: "{code:Runtime}\venv\pythonw.exe"; Parameters: "-E -s -X utf8 ""{code:Runtime}\install.py"" panel"; Description: "Open Claude Thinking Translation"; Flags: postinstall nowait skipifsilent

[Code]
var
  RuntimeDownload: TDownloadWizardPage;

procedure InitializeWizard;
begin
  RuntimeDownload := CreateDownloadPage('Visual C++ Runtime', 'Installing the Microsoft runtime required for offline translation.', nil);
end;

function Runtime(Param: String): String;
begin
  Result := GetEnv('LOCALAPPDATA');
  if Result = '' then Result := ExpandConstant('{localappdata}');
  Result := AddBackslash(Result) + 'claude-thinking-translation';
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Installed, Minor: Cardinal;
  Code: Integer;
  FilePath, LiteralPath, Verify: String;
begin
  Result := '';
  if DirExists(Runtime('')) or FileExists(Runtime('')) then begin
    Result := '已存在 Claude 思考翻译。请先在原面板恢复直连并卸载已有版本。';
    exit;
  end;
  if RegQueryDWordValue(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Installed) and
     RegQueryDWordValue(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Minor', Minor) and
     (Installed = 1) and (Minor >= 40) then exit;
  RuntimeDownload.Clear;
  RuntimeDownload.Add('https://aka.ms/vc14/vc_redist.x64.exe', 'vc_redist.x64.exe', '');
  RuntimeDownload.Show;
  try
    try
      RuntimeDownload.Download;
    except
      Result := '无法下载 Microsoft Visual C++ 运行库。请连接网络后重试。';
      exit;
    end;
  finally
    RuntimeDownload.Hide;
  end;
  FilePath := ExpandConstant('{tmp}\vc_redist.x64.exe');
  LiteralPath := FilePath;
  StringChangeEx(LiteralPath, #39, #39#39, True);
  Verify := '$s = Get-AuthenticodeSignature -LiteralPath ' + #39 + LiteralPath + #39 +
            '; if ($s.Status -ne ''Valid'' -or $s.SignerCertificate.Subject -notmatch ''(^|, )O=Microsoft Corporation(,|$)'') { exit 1 }';
  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
              '-NoProfile -NonInteractive -Command "' + Verify + '"', '', SW_HIDE, ewWaitUntilTerminated, Code) or (Code <> 0) then begin
    Result := 'Microsoft 运行库签名校验失败。';
    exit;
  end;
  if not ShellExec('runas', FilePath, '/install /quiet /norestart', '', SW_HIDE, ewWaitUntilTerminated, Code) or
     ((Code <> 0) and (Code <> 3010) and (Code <> 1638)) then
    Result := 'Microsoft 运行库安装未完成。请按系统提示允许安装后重试。'
  else if Code = 3010 then begin
    NeedsRestart := True;
    Result := 'Microsoft 运行库需要重启 Windows。重启后请再次打开安装包。';
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Code: Integer;
  Source: String;
begin
  if CurStep = ssPostInstall then begin
    Source := ExpandConstant('{tmp}\payload');
    if not ExecAndLogOutput(Source + '\venv\python.exe', '-E -s -X utf8 "' + Source + '\install.py" install --no-open',
                           Source, SW_SHOW, ewWaitUntilTerminated, Code, nil) or (Code <> 0) then
      RaiseException('翻译服务安装或自检失败。请查看安装日志。');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Code, Attempt: Integer;
  Directory: String;
begin
  if CurUninstallStep <> usUninstall then exit;
  Directory := Runtime('');
  Log('Checking translation runtime at ' + Directory);
  if not DirExists(Directory) then exit;
  if not FileExists(Directory + '\.installed-by-package') or
     not ExecAndLogOutput(Directory + '\venv\python.exe', '-E -s -X utf8 "' + Directory + '\install.py" prepare-uninstall',
                          Directory, SW_SHOW, ewWaitUntilTerminated, Code, nil) or (Code <> 0) then
    RaiseException('请先在翻译面板恢复 Desktop 和 CLI 直连，退出相关会话，再试一次卸载。');
  for Attempt := 1 to 20 do begin
    if DelTree(Directory, True, True, True) or not DirExists(Directory) then exit;
    Sleep(150);
  end;
  RaiseException('翻译目录仍在使用。请关闭翻译会话后重试。');
end;
