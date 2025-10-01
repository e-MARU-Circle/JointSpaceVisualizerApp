; JointSpaceVisualizer Windows Installer Script
; Requires NSIS (https://nsis.sourceforge.io/) and assumes PyInstaller output exists at dist/JointSpaceVisualizer

!ifndef ROOT_DIR
  !define ROOT_DIR "..\.."
!endif

!define APP_NAME "Joint Space Visualizer"
!define COMPANY_KEY "JointSpaceVisualizer"
!define INSTALL_DIR "$PROGRAMFILES64\\JointSpaceVisualizer"

!include "MUI2.nsh"

!define MUI_STARTMENUPAGE_REGISTRY_ROOT "HKCU"
!define MUI_STARTMENUPAGE_REGISTRY_KEY "Software\${COMPANY_KEY}"
!define MUI_STARTMENUPAGE_REGISTRY_VALUENAME "StartMenuFolder"
!define MUI_STARTMENUPAGE_DEFAULTFOLDER "${APP_NAME}"

Name "${APP_NAME}"
OutFile "JointSpaceVisualizerSetup.exe"
InstallDir "${INSTALL_DIR}"
InstallDirRegKey HKCU "Software\\${COMPANY_KEY}" "InstallDir"
RequestExecutionLevel admin

!define MUI_ABORTWARNING

Var StartMenuFolder

!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_STARTMENU Application $StartMenuFolder
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Japanese"

Section "Install"
  SetOutPath "$INSTDIR"

  ; Bundle everything produced by PyInstaller.
  File /r "${ROOT_DIR}\dist\JointSpaceVisualizer\*"

  ; Store installation path for future upgrades
  WriteRegStr HKCU "Software\\${COMPANY_KEY}" "InstallDir" "$INSTDIR"

  ; Desktop shortcut
  CreateShortcut "$DESKTOP\\${APP_NAME}.lnk" "$INSTDIR\\JointSpaceVisualizer.exe"

  ; Start menu shortcut folder
  !insertmacro MUI_STARTMENU_WRITE_BEGIN Application
    CreateDirectory "$SMPROGRAMS\\$StartMenuFolder"
    CreateShortcut "$SMPROGRAMS\\$StartMenuFolder\\${APP_NAME}.lnk" "$INSTDIR\\JointSpaceVisualizer.exe"
    CreateShortcut "$SMPROGRAMS\\$StartMenuFolder\\Uninstall ${APP_NAME}.lnk" "$INSTDIR\\Uninstall.exe"
  !insertmacro MUI_STARTMENU_WRITE_END

  ; Uninstaller
  WriteUninstaller "$INSTDIR\\Uninstall.exe"
SectionEnd

Section "Uninstall"
  ; Remove shortcuts
  Delete "$DESKTOP\\${APP_NAME}.lnk"
  !insertmacro MUI_STARTMENU_GETFOLDER Application $StartMenuFolder
  Delete "$SMPROGRAMS\\$StartMenuFolder\\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\\$StartMenuFolder\\Uninstall ${APP_NAME}.lnk"
  RMDir "$SMPROGRAMS\\$StartMenuFolder"

  ; Remove installed files
  Delete "$INSTDIR\\Uninstall.exe"
  RMDir /r "$INSTDIR"

  ; Registry cleanup
  DeleteRegKey HKCU "Software\\${COMPANY_KEY}"
SectionEnd
