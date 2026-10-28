Unicode true

!include "MUI2.nsh"
!include "LogicLib.nsh"

!ifndef PRODUCT_VERSION
  !error "PRODUCT_VERSION must be provided by the release package job."
!endif
!ifndef CANOPY_BUNDLE_DIR
  !error "CANOPY_BUNDLE_DIR must point to the extracted Windows bundle."
!endif
!ifndef CANOPY_NSIS_OUTPUT
  !error "CANOPY_NSIS_OUTPUT must be set by the build job."
!endif

!define PRODUCT_NAME "Canopy Exploration Processor"
!define PRODUCT_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\CanopyExplorationProcessor"
!define PRODUCT_VERSION_QUAD "${PRODUCT_VERSION}.0"

Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "$%CANOPY_NSIS_OUTPUT%"
InstallDir "$LOCALAPPDATA\Canopy Exploration Processor"
InstallDirRegKey HKCU "${PRODUCT_KEY}" "InstallLocation"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails show
ShowUnInstDetails show
ManifestDPIAware true
VIProductVersion "${PRODUCT_VERSION_QUAD}"
VIAddVersionKey "ProductName" "${PRODUCT_NAME}"
VIAddVersionKey "CompanyName" "Michelin"
VIAddVersionKey "FileDescription" "Canopy Exploration Processor installer"
VIAddVersionKey "FileVersion" "${PRODUCT_VERSION_QUAD}"
VIAddVersionKey "ProductVersion" "${PRODUCT_VERSION}"

!ifdef CANOPY_SIGN_RELEASE
  !finalize '"powershell.exe" -NoProfile -NonInteractive -File "$%CANOPY_SIGNING_WRAPPER%" -Path "%1" -Kind Executable' = 0
  !uninstfinalize '"powershell.exe" -NoProfile -NonInteractive -File "$%CANOPY_SIGNING_WRAPPER%" -Path "%1" -Kind Executable' = 0
!endif

!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function CanopyExplorationProcessorCheckExistingInstall
  IfFileExists "$INSTDIR\deployment.ps1" 0 done
  StrCpy $0 1
  ExecWait '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -File "$INSTDIR\deployment.ps1" -Mode CheckIdle -InstallDirectory "$INSTDIR"' $0
  StrCmp $0 0 done
  MessageBox MB_ICONSTOP "Close all Canopy Exploration Processor sessions and verify installation-folder permissions before continuing."
  Abort
done:
FunctionEnd

Function un.CanopyExplorationProcessorCheckExistingInstall
  IfFileExists "$INSTDIR\deployment.ps1" 0 done
  StrCpy $0 1
  ExecWait '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -File "$INSTDIR\deployment.ps1" -Mode CheckIdle -InstallDirectory "$INSTDIR"' $0
  StrCmp $0 0 done
  MessageBox MB_ICONSTOP "Close all Canopy Exploration Processor sessions and verify installation-folder permissions before uninstalling."
  Abort
done:
FunctionEnd

Function un.onInit
  ReadRegStr $INSTDIR HKCU "${PRODUCT_KEY}" "InstallLocation"
  Call un.CanopyExplorationProcessorCheckExistingInstall
FunctionEnd

Section "Install Canopy Exploration Processor" SEC_CANOPY_EXPLORATION_PROCESSOR
  Call CanopyExplorationProcessorCheckExistingInstall
  SetOutPath "$INSTDIR"
  File "$%CANOPY_BUNDLE_DIR%\deployment.ps1"
  File "$%CANOPY_BUNDLE_DIR%\cleanup.py"
  File "$%CANOPY_BUNDLE_DIR%\setup_environment.bat"
  File "$%CANOPY_BUNDLE_DIR%\CanopyExplorationStart.bat"
  File "$%CANOPY_BUNDLE_DIR%\remove_environment.bat"

  SetOutPath "$INSTDIR\payload"
  File "$%CANOPY_BUNDLE_DIR%\payload\release.json"
  File "$%CANOPY_BUNDLE_DIR%\payload\canopy_exploration_processor-${PRODUCT_VERSION}-py3-none-any.whl"

  StrCpy $0 1
  ExecWait '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -File "$INSTDIR\deployment.ps1" -Mode Setup -ReleaseVersion "${PRODUCT_VERSION}" -InstallDirectory "$INSTDIR"' $0
  ${If} $0 != 0
    MessageBox MB_ICONSTOP "Canopy Exploration Processor setup failed. See $LOCALAPPDATA\CanopyExplorationProcessor\logs\deployment.log."
    Abort
  ${EndIf}

  SetOutPath "$INSTDIR"
  WriteUninstaller "$INSTDIR\uninst.exe"
  CreateDirectory "$SMPROGRAMS\Canopy Exploration Processor"
  CreateShortCut "$SMPROGRAMS\Canopy Exploration Processor\Canopy Exploration Processor.lnk" "$INSTDIR\CanopyExplorationStart.bat" "" "" "" SW_SHOWNORMAL
  CreateShortCut "$SMPROGRAMS\Canopy Exploration Processor\Uninstall.lnk" "$INSTDIR\uninst.exe"
  WriteRegStr HKCU "${PRODUCT_KEY}" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr HKCU "${PRODUCT_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKCU "${PRODUCT_KEY}" "Publisher" "Michelin"
  WriteRegStr HKCU "${PRODUCT_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${PRODUCT_KEY}" "UninstallString" '"$INSTDIR\uninst.exe"'
SectionEnd

Section "Uninstall"
  IfFileExists "$INSTDIR\deployment.ps1" 0 remove_owned_files
  StrCpy $0 1
  ExecWait '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -File "$INSTDIR\deployment.ps1" -Mode Remove -InstallDirectory "$INSTDIR"' $0
  ${If} $0 != 0
    MessageBox MB_ICONSTOP "Canopy Exploration Processor environment removal failed. Close all sessions, check the deployment log and retry."
    Abort
  ${EndIf}

remove_owned_files:
  Delete "$SMPROGRAMS\Canopy Exploration Processor\Canopy Exploration Processor.lnk"
  Delete "$SMPROGRAMS\Canopy Exploration Processor\Uninstall.lnk"
  RMDir "$SMPROGRAMS\Canopy Exploration Processor"
  DeleteRegKey HKCU "${PRODUCT_KEY}"
  Delete "$INSTDIR\deployment.ps1"
  Delete "$INSTDIR\cleanup.py"
  Delete "$INSTDIR\setup_environment.bat"
  Delete "$INSTDIR\CanopyExplorationStart.bat"
  Delete "$INSTDIR\remove_environment.bat"
  Delete "$INSTDIR\uninst.exe"
  Delete "$INSTDIR\.deployment.lock"
  Delete "$INSTDIR\payload\*.*"
  RMDir "$INSTDIR\payload"
  RMDir "$INSTDIR\envs"
  RMDir "$INSTDIR"
SectionEnd