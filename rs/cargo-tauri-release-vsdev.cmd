@echo off
setlocal

set "VS2022=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat"
set "VS18=C:\Program Files\Microsoft Visual Studio\18\BuildTools\Common7\Tools\VsDevCmd.bat"

if exist "%VS2022%" (
  call "%VS2022%" -arch=x64
) else if exist "%VS18%" (
  call "%VS18%" -arch=x64
) else (
  echo Could not find a supported Visual Studio developer command prompt.
  exit /b 1
)

if errorlevel 1 exit /b %errorlevel%

cargo tauri build
