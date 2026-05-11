Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
root = fso.GetParentFolderName(fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName)))
shell.CurrentDirectory = root
shell.Run Chr(34) & "cmd.exe" & Chr(34) & " /c start.bat", 0, False
