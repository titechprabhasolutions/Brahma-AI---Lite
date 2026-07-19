Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
venvPython = root & "\.venv\Scripts\pythonw.exe"
mainPy = root & "\main.py"

If fso.FileExists(venvPython) Then
  shell.Run Chr(34) & venvPython & Chr(34) & " " & Chr(34) & mainPy & Chr(34) & " --startup", 0, False
ElseIf fso.FileExists(root & "\pythonw.exe") Then
  shell.Run Chr(34) & root & "\pythonw.exe" & Chr(34) & " " & Chr(34) & mainPy & Chr(34) & " --startup", 0, False
Else
  shell.Run "python.exe " & Chr(34) & mainPy & Chr(34) & " --startup", 0, False
End If
