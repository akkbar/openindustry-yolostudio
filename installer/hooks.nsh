; Application files are installed system-wide. User data is never removed.
!macro NSIS_HOOK_POSTINSTALL
  CreateShortCut "$DESKTOP\OpenIndustry Vision Studio.lnk" "$INSTDIR\OpenIndustry Vision Studio.exe"
!macroend

!macro NSIS_HOOK_POSTUNINSTALL
  Delete "$DESKTOP\OpenIndustry Vision Studio.lnk"
!macroend
