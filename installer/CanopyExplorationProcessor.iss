#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif

[Setup]
AppId={{B8651CE7-CE87-46C4-889F-5437C544C20B}
AppName=Canopy Exploration Processor
AppVersion={#MyAppVersion}
DefaultDirName=C:\Bib\Prod\CanopyExplorationProcessor
DefaultGroupName=Canopy Exploration Processor
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=output
OutputBaseFilename=CanopyExplorationProcessor-{#MyAppVersion}-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=no
RestartApplications=no
UninstallDisplayName=Canopy Exploration Processor

[Files]
Source: "deployment.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "setup_environment.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "CanopyExplorationStart.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "CanopyExplorationUpdate.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "remove_environment.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\DISTRIBUTION.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Canopy Exploration Processor"; Filename: "{app}\CanopyExplorationStart.bat"; WorkingDir: "{app}"
Name: "{group}\Update Canopy Exploration Processor"; Filename: "{app}\CanopyExplorationUpdate.bat"; WorkingDir: "{app}"
Name: "{group}\Uninstall"; Filename: "{uninstallexe}"

[UninstallDelete]
Type: files; Name: "{app}\.deployment.lock"
Type: dirifempty; Name: "{app}\envs"

[Code]
function RunDeployment(Mode: String): Boolean;
var
  ResultCode: Integer;
  Parameters: String;
begin
  Parameters := '-NoProfile -File "' + ExpandConstant('{app}\deployment.ps1') + '" -Mode ' + Mode;
  if Mode = 'Setup' then
    Parameters := Parameters + ' -ReleaseVersion {#MyAppVersion}';
  Result := Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    Parameters,
    ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if Result then
    Result := ResultCode = 0;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if FileExists(ExpandConstant('{app}\deployment.ps1')) then
    if not RunDeployment('CheckIdle') then
      Result := 'Close Canopy and verify installation-folder permissions before continuing.';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    if not RunDeployment('Setup') then
      RaiseException('Environment setup failed. See %LOCALAPPDATA%\CanopyExplorationProcessor\logs\deployment.log.');
end;

function InitializeUninstall(): Boolean;
begin
  Result := RunDeployment('CheckIdle');
  if not Result then
    MsgBox('Close Canopy and verify installation-folder permissions before uninstalling.', mbError, MB_OK);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    if not RunDeployment('Remove') then
      RaiseException('Environment removal failed. Close Canopy and retry uninstalling.');
end;