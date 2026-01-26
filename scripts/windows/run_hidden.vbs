Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptPath = fso.GetParentFolderName(WScript.ScriptFullName)
projectRoot = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
batPath = scriptPath & "\run_archiver.bat"
WshShell.Run chr(34) & batPath & chr(34), 0
Set WshShell = Nothing
