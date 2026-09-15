!macro NSIS_HOOK_POSTINSTALL
  CreateShortCut "$DESKTOP\Vision Studio QA.lnk" "$INSTDIR\VisionStudio.exe"
!macroend

!macro NSIS_HOOK_POSTUNINSTALL
  Delete "$DESKTOP\Vision Studio QA.lnk"
!macroend
