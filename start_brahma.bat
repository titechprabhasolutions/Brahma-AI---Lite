@echo off
setlocal EnableExtensions EnableDelayedExpansion

title Brahma AI - Lite - Premium Launcher
cd /d "%~dp0"

set "ROOT=%~dp0"
set "VENV=%ROOT%.venv"
set "PYTHON=%VENV%\Scripts\python.exe"
set "PYW=%VENV%\Scripts\pythonw.exe"
set "MAIN=%ROOT%main.py"
set "REQUIREMENTS=%ROOT%requirements.txt"
set "PYCMD="

echo.
echo ==============================================
echo      Brahma AI - Lite  ^| Premium Launcher
echo ==============================================
echo.

if exist "%PYTHON%" (
  set "PYCMD=%PYTHON%"
)

if not defined PYCMD if exist "%ROOT%python.exe" (
  set "PYCMD=%ROOT%python.exe"
)

if not defined PYCMD if exist "%SystemRoot%\py.exe" (
  set "PYCMD=%SystemRoot%\py.exe"
)

if not defined PYCMD (
  for /f "delims=" %%I in ('where.exe py 2^>nul') do (
    set "CAND=%%~I"
    if exist "!CAND!" (
      set "PYCMD=!CAND!"
      goto :foundPython
    )
  )
)

if not defined PYCMD (
  for /f "delims=" %%I in ('where.exe python 2^>nul') do (
    set "CAND=%%~I"
    echo !CAND! | findstr /i "WindowsApps" >nul
    if errorlevel 1 if exist "!CAND!" (
      set "PYCMD=!CAND!"
      goto :foundPython
    )
  )
)

if not defined PYCMD (
  for /f "delims=" %%I in ('where.exe python3 2^>nul') do (
    set "CAND=%%~I"
    echo !CAND! | findstr /i "WindowsApps" >nul
    if errorlevel 1 if exist "!CAND!" (
      set "PYCMD=!CAND!"
      goto :foundPython
    )
  )
)

:foundPython
if not defined PYCMD (
  echo ERROR: No Python interpreter found. Install Python 3.11 or 3.12 and retry.
  pause
  exit /b 1
)

echo Using bootstrap Python: "%PYCMD%"

if exist "%VENV%" if not exist "%PYTHON%" (
  echo Found broken virtual environment. Recreating .venv...
  rmdir /s /q "%VENV%"
)

if not exist "%PYTHON%" (
  echo Creating local virtual environment...
  "%PYCMD%" -m venv "%VENV%" || goto :fallback
  echo Virtual environment created.
)

if exist "%PYTHON%" (
  set "PYCMD=%PYTHON%"
) else if exist "%PYW%" (
  set "PYCMD=%PYW%"
) else (
  echo ERROR: Python was not found inside the created virtual environment.
  pause
  exit /b 1
)

echo Using virtual environment Python: "%PYCMD%"

echo.
echo Installing and validating dependencies...
"%PYCMD%" -m pip install --upgrade pip setuptools wheel
"%PYCMD%" -m pip install -r "%REQUIREMENTS%"

if %errorlevel% neq 0 (
  echo ERROR: Dependency installation failed.
  pause
  exit /b 2
)

echo.
echo Installing Playwright browsers...
"%PYCMD%" -m playwright install

if %errorlevel% neq 0 (
  echo ERROR: Playwright installation failed.
  pause
  exit /b 3
)

echo.
echo Launching Brahma AI...
if exist "%PYW%" (
  start "Brahma AI - Lite" /b "%PYW%" "%MAIN%" --startup
) else (
  start "Brahma AI - Lite" /b "%PYCMD%" "%MAIN%" --startup
)

echo Launcher complete.
exit /b 0

:fallback
echo ERROR: Failed to create the virtual environment.
pause
exit /b 4
