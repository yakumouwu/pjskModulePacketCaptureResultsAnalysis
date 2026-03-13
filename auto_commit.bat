@echo off
setlocal
cd /d D:\reverse
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse\auto_commit.ps1"
exit /b %errorlevel%

