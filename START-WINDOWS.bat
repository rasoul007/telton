@echo off
chcp 65001 >nul
title tooop news
cd /d "%~dp0"

set "PY=python"
where py >nul 2>nul && set "PY=py -3"

%PY% "scripts\launcher.py"
if errorlevel 1 (
  echo.
  echo اگر خطایی دیدی، همین پنجره را برای پشتیبانی بفرست.
  pause
)
