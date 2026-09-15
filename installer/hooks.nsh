; Application files are installed system-wide. User data is never removed.
!macro NSIS_HOOK_POSTINSTALL
  CreateShortCut "$DESKTOP\VisionStudio.lnk" "$INSTDIR\VisionStudio.exe"
!macroend

!macro NSIS_HOOK_POSTUNINSTALL
  Delete "$DESKTOP\VisionStudio.lnk"
!macroend
