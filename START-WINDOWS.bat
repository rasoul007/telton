@echo off
chcp 65001 >nul
title tooop news
cd /d "%~dp0"

echo.
echo   tooop news - starting...
echo.

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY goto nopython

%PY% "scripts\launcher.py"
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
  echo.
  echo   Something went wrong. Take a screenshot of this window and send it.
  pause
)
exit /b %CODE%

:nopython
echo   Python is not installed.
echo.
echo   1^) Open https://www.python.org/downloads/
echo   2^) Run the installer and CHECK the box: Add python.exe to PATH
echo   3^) Then double-click START-WINDOWS.bat again
echo.
pause
exit /b 1
