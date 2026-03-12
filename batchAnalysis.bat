@echo off
setlocal

set "CONDA_ACT=E:\ProgramData\miniconda3\Scripts\activate.bat"
set "ENV_NAME=pjsk"
set "SCRIPT_PATH=D:\reverse\01_scripts\import http.py"

if not exist "%CONDA_ACT%" (
  echo [ERROR] conda activate script not found: %CONDA_ACT%
  pause
  exit /b 1
)

if not exist "%SCRIPT_PATH%" (
  echo [ERROR] script not found: %SCRIPT_PATH%
  pause
  exit /b 1
)

call "%CONDA_ACT%" %ENV_NAME%
if errorlevel 1 (
  echo [ERROR] failed to activate conda env: %ENV_NAME%
  pause
  exit /b 1
)

echo [INFO] Running %SCRIPT_PATH% in conda env %ENV_NAME%...
python "%SCRIPT_PATH%"
set "RC=%ERRORLEVEL%"

echo.
echo [INFO] Script exited with code %RC%
pause
exit /b %RC%

