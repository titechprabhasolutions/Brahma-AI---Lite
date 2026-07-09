Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
pyw = "C:\Users\ravit\AppData\Local\Programs\Python\Python313\pythonw.exe"
mainPy = root & "\main.py"
If fso.FileExists(pyw) Then
  shell.Run Chr(34) & pyw & Chr(34) & " " & Chr(34) & mainPy & Chr(34) & " --startup", 0, False
Else
  shell.Run "python.exe " & Chr(34) & mainPy & Chr(34) & " --startup", 0, False
End If
