!macro NSIS_HOOK_POSTINSTALL
  CreateShortCut "$DESKTOP\OpenIndustry Vision Studio QA.lnk" "$INSTDIR\OpenIndustry Vision Studio.exe"
!macroend

!macro NSIS_HOOK_POSTUNINSTALL
  Delete "$DESKTOP\OpenIndustry Vision Studio QA.lnk"
!macroend
