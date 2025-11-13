@echo off
setlocal

REM Usage: set CERT_PATH=path\to\cert.pfx & set CERT_PASSWORD=xxxx & call sign.bat
if "%CERT_PATH%"=="" (
  echo Set CERT_PATH to your PFX file path.
  exit /b 1
)
if "%CERT_PASSWORD%"=="" (
  echo Set CERT_PASSWORD to your certificate password.
  exit /b 1
)
if "%TIMESTAMP_URL%"=="" set TIMESTAMP_URL=http://timestamp.digicert.com

where signtool >nul 2>&1 || (echo signtool not found. Install Windows SDK. & exit /b 1)

if exist dist\Veo3App.exe (
  echo Signing Veo3App.exe ...
  signtool sign /fd SHA256 /f "%CERT_PATH%" /p "%CERT_PASSWORD%" /tr %TIMESTAMP_URL% /td SHA256 "dist\Veo3App.exe" || exit /b 1
)

if exist dist\Veo3Setup.exe (
  echo Signing Veo3Setup.exe ...
  signtool sign /fd SHA256 /f "%CERT_PATH%" /p "%CERT_PASSWORD%" /tr %TIMESTAMP_URL% /td SHA256 "dist\Veo3Setup.exe" || exit /b 1
)

echo Done.
endlocal


