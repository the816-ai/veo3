@echo off
setlocal

REM Kiem tra Python
where python >nul 2>&1
if errorlevel 1 (
	echo Khong tim thay Python trong PATH. Vui long cai dat Python 3.9+.
	pause
	exit /b 1
)

REM Kiem tra FFmpeg
where ffmpeg >nul 2>&1
if errorlevel 1 (
	echo Khong tim thay FFmpeg trong PATH. Vui long cai dat FFmpeg va mo lai file nay.
	pause
	exit /b 1
)

REM Tao venv (tuy chon)
if not exist .venv (
	python -m venv .venv
)
call .venv\Scripts\activate.bat

REM Cai dat thu vien
python -m pip install --upgrade pip
pip install -r requirements.txt

REM Chay ung dung
echo Dang chay ung dung...
python main.py

endlocal
