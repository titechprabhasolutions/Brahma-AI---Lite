@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "VBS=%ROOT%start_brahma.vbs"
set "PYW=C:\Users\ravit\AppData\Local\Programs\Python\Python313\pythonw.exe"
set "MAIN=%ROOT%main.py"

title Brahma AI - Lite Launcher

if exist "%VBS%" (
    wscript.exe "%VBS%"
    exit /b 0
)

if exist "%PYW%" (
    start "" /b "%PYW%" "%MAIN%" --startup
    exit /b 0
)

python.exe "%MAIN%" --startup
exit /b %errorlevel%
