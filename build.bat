@echo off
setlocal

REM Clean dist
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM Ensure Python and pip
where python >nul 2>&1 || (echo Python is required. & exit /b 1)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller requests

REM Download portable FFmpeg (win64) if missing to .\ffmpeg\bin
set FFMPEG_DIR=%~dp0ffmpeg\bin
if not exist "%FFMPEG_DIR%" (
    mkdir "%FFMPEG_DIR%"
)
if not exist "%FFMPEG_DIR%\ffmpeg.exe" (
    echo Downloading FFmpeg (ZIP)...
    set FFZIP=ffmpeg-win64.zip
    powershell -NoProfile -ExecutionPolicy Bypass -Command "& { $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip' -OutFile '%FFZIP%' }" || goto :download_fail
    echo Extracting FFmpeg...
    set EXTRACT_DIR=_ffmpeg_extract
    if exist %EXTRACT_DIR% rmdir /s /q %EXTRACT_DIR%
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%FFZIP%' -DestinationPath '%EXTRACT_DIR%' -Force" || goto :extract_fail
    for /r "%EXTRACT_DIR%" %%F in (ffmpeg.exe) do (
        xcopy /y /i "%%F" "%FFMPEG_DIR%\" >nul
    )
    for /r "%EXTRACT_DIR%" %%F in (ffprobe.exe) do (
        xcopy /y /i "%%F" "%FFMPEG_DIR%\" >nul
    )
)

REM Build single-file exe
set NAME=Veo3App
set ENTRY=main.py
pyinstaller --onefile --noconsole --name %NAME% ^
  --add-binary "%FFMPEG_DIR%\ffmpeg.exe;." ^
  --add-binary "%FFMPEG_DIR%\ffprobe.exe;." ^
  %ENTRY%
if errorlevel 1 goto :end

echo Build complete: dist\%NAME%.exe

REM Optional: build installer with Inno Setup (iscc)
where iscc >nul 2>&1
if %errorlevel%==0 (
  echo Building installer...
  iscc installer.iss || echo Inno Setup build failed.
) else (
  echo Inno Setup (iscc) not found. Skip installer build.
)

echo Optional signing: set CERT_PATH and CERT_PASSWORD then run sign.bat
exit /b 0

:download_fail
echo Failed to download FFmpeg. Check your internet connection.
goto :end

:extract_fail
echo Failed to extract FFmpeg ZIP. You can manually extract and place ffmpeg.exe and ffprobe.exe into .\ffmpeg\bin\ then rerun.

goto :end

:end
endlocal
