$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('C:\Users\ravit\Desktop\Brahma AI - Lite.lnk')
$Shortcut.TargetPath = 'C:\Users\ravit\AppData\Local\Programs\Python\Python313\python.exe'
$Shortcut.Arguments = '"D:\TiTech Prabha Solution\Brahma AI\Brahma AI\Brahma AI - Lite\main.py"'
$Shortcut.WorkingDirectory = 'D:\TiTech Prabha Solution\Brahma AI\Brahma AI\Brahma AI - Lite'
$Shortcut.WindowStyle = 7
$Shortcut.Description = 'Launch Brahma AI - Lite'
if ('D:\TiTech Prabha Solution\Brahma AI\Brahma AI\Brahma AI - Lite\assets\Brahma_Lite_Logo.ico') { $Shortcut.IconLocation = 'D:\TiTech Prabha Solution\Brahma AI\Brahma AI\Brahma AI - Lite\assets\Brahma_Lite_Logo.ico,0' }
$Shortcut.Save()