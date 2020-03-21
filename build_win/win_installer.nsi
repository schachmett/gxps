; This windows building routine was largely adopted from the
; Quod Libet project 
; https://github.com/quodlibet/quodlibet (Copyright 2016 Christoph Reiter)

Unicode true

!define GXPS_NAME "GXPS"
!define GXPS_ID "gxps"
!define GXPS_DESC "Science / Plotting / Spectroscopy"

!define GXPS_WEBSITE "https://github.com/schachmett/gxps"

!define GXPS_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${GXPS_NAME}"
!define GXPS_INSTDIR_KEY "Software\${GXPS_NAME}"
!define GXPS_INSTDIR_VALUENAME "InstDir"

!define MUI_CUSTOMFUNCTION_GUIINIT custom_gui_init
!include "MUI2.nsh"
!include "FileFunc.nsh"

Name "${GXPS_NAME} (${VERSION})"
OutFile "gxps-LATEST.exe"
SetCompressor /SOLID /FINAL lzma
SetCompressorDictSize 32
InstallDir "$PROGRAMFILES\${GXPS_NAME}"
RequestExecutionLevel admin

Var GXPS_INST_BIN
Var UNINST_BIN

!define MUI_ABORTWARNING
!define MUI_ICON "..\gxps.ico"

!insertmacro MUI_PAGE_LICENSE "..\gxps\gxps\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"


Section "Install"
    SetShellVarContext all

    ; Use this to make things faster for testing installer changes
    ;~ SetOutPath "$INSTDIR\bin"
    ;~ File /r "mingw32\bin\*.exe"

    SetOutPath "$INSTDIR"
    File /r "*.*"

    StrCpy $GXPS_INST_BIN "$INSTDIR\bin\gxps.exe"
    StrCpy $UNINST_BIN "$INSTDIR\uninstall.exe"

    ; Store installation folder
    WriteRegStr HKLM "${GXPS_INSTDIR_KEY}" "${GXPS_INSTDIR_VALUENAME}" $INSTDIR

    ; Set up an entry for the uninstaller
    WriteRegStr HKLM "${GXPS_UNINST_KEY}" "DisplayName" "${GXPS_NAME} - ${GXPS_DESC}"
    WriteRegStr HKLM "${GXPS_UNINST_KEY}" "DisplayIcon" "$\"$GXPS_INST_BIN$\""
    WriteRegStr HKLM "${GXPS_UNINST_KEY}" "UninstallString" "$\"$UNINST_BIN$\""
    WriteRegStr HKLM "${GXPS_UNINST_KEY}" "QuietUninstallString" "$\"$UNINST_BIN$\" /S"
    WriteRegStr HKLM "${GXPS_UNINST_KEY}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "${GXPS_UNINST_KEY}" "HelpLink" "${GXPS_WEBSITE}"
    WriteRegStr HKLM "${GXPS_UNINST_KEY}" "Publisher" "The ${GXPS_NAME} Development Community"
    WriteRegStr HKLM "${GXPS_UNINST_KEY}" "DisplayVersion" "${VERSION}"
    WriteRegDWORD HKLM "${GXPS_UNINST_KEY}" "NoModify" 0x1
    WriteRegDWORD HKLM "${GXPS_UNINST_KEY}" "NoRepair" 0x1
    ; Installation size
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "${GXPS_UNINST_KEY}" "EstimatedSize" "$0"

    ; Register a default entry for file extensions
    WriteRegStr HKLM "Software\Classes\${GXPS_ID}.assoc.ANY\DefaultIcon" "" "$\"$GXPS_INST_BIN$\""

    ; Add application entry
    WriteRegStr HKLM "Software\${GXPS_NAME}\${GXPS_ID}\Capabilities" "ApplicationDescription" "${GXPS_DESC}"
    WriteRegStr HKLM "Software\${GXPS_NAME}\${GXPS_ID}\Capabilities" "ApplicationName" "${GXPS_NAME}"

    ; Register supported file extensions
    ; (generated using gen_supported_types.py)
    !define GXPS_ASSOC_KEY "Software\${GXPS_NAME}\${GXPS_ID}\Capabilities\FileAssociations"
    WriteRegStr HKLM "${GXPS_ASSOC_KEY}" ".gxps" "${GXPS_ID}.assoc.ANY"

    ; Register application entry
    WriteRegStr HKLM "Software\RegisteredApplications" "${GXPS_NAME}" "Software\${GXPS_NAME}\${GXPS_ID}\Capabilities"

    ; Register app paths
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\App Paths\gxps.exe" "" "$GXPS_INST_BIN"

    ; Create uninstaller
    WriteUninstaller "$UNINST_BIN"

    ; Create start menu shortcuts
    CreateDirectory "$SMPROGRAMS\${GXPS_NAME}"
    CreateShortCut "$SMPROGRAMS\${GXPS_NAME}\${GXPS_NAME}.lnk" "$GXPS_INST_BIN"
SectionEnd

Function custom_gui_init
    BringToFront

    ; Read the install dir and set it
    Var /GLOBAL instdir_temp
    Var /GLOBAL uninst_bin_temp

    SetRegView 32
    ReadRegStr $instdir_temp HKLM "${GXPS_INSTDIR_KEY}" "${GXPS_INSTDIR_VALUENAME}"
    SetRegView lastused
    StrCmp $instdir_temp "" skip 0
        StrCpy $INSTDIR $instdir_temp
    skip:

    SetRegView 64
    ReadRegStr $instdir_temp HKLM "${GXPS_INSTDIR_KEY}" "${GXPS_INSTDIR_VALUENAME}"
    SetRegView lastused
    StrCmp $instdir_temp "" skip2 0
        StrCpy $INSTDIR $instdir_temp
    skip2:

    StrCpy $uninst_bin_temp "$INSTDIR\uninstall.exe"

    ; try to un-install existing installations first
    IfFileExists "$INSTDIR" do_uninst do_continue
    do_uninst:
        ; instdir exists
        IfFileExists "$uninst_bin_temp" exec_uninst rm_instdir
        exec_uninst:
            ; uninstall.exe exists, execute it and
            ; if it returns success proceed, otherwise abort the
            ; installer (uninstall aborted by user for example)
            ExecWait '"$uninst_bin_temp" _?=$INSTDIR' $R1
            ; uninstall succeeded, since the uninstall.exe is still there
            ; goto rm_instdir as well
            StrCmp $R1 0 rm_instdir
            ; uninstall failed
            Abort
        rm_instdir:
            ; either the uninstaller was successfull or
            ; the uninstaller.exe wasn't found
            RMDir /r "$INSTDIR"
    do_continue:
        ; the instdir shouldn't exist from here on

    BringToFront
FunctionEnd

Section "Uninstall"
    SetShellVarContext all
    SetAutoClose true

    ; Remove start menu entries
    Delete "$SMPROGRAMS\${GXPS_NAME}\${GXPS_NAME}.lnk"
    RMDir "$SMPROGRAMS\${GXPS_NAME}"

    ; Remove application registration and file assocs
    DeleteRegKey HKLM "Software\Classes\${GXPS_ID}.assoc.ANY"
    DeleteRegKey HKLM "Software\${GXPS_NAME}"
    DeleteRegValue HKLM "Software\RegisteredApplications" "${GXPS_NAME}"

    ; Remove app paths
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\App Paths\gxps.exe"

    ; Delete installation related keys
    DeleteRegKey HKLM "${GXPS_UNINST_KEY}"
    DeleteRegKey HKLM "${GXPS_INSTDIR_KEY}"

    ; Delete files
    RMDir /r "$INSTDIR"
SectionEnd
