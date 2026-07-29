@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo Sanal ortam bulunamadÄ±. Ã–nce scripts\kurulum.bat Ã§alÄ±ÅŸtÄ±rÄ±n.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
pip install -r requirements-dev.txt
if errorlevel 1 goto :error

rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

pyinstaller --noconfirm --clean --windowed --onedir --name KolayIndir --collect-all yt_dlp app.py
if errorlevel 1 goto :error

echo.
echo Derleme tamamlandÄ±: dist\KolayIndir\KolayIndir.exe
pause
exit /b 0

:error
echo.
echo EXE oluÅŸturulurken hata oluÅŸtu.
pause
exit /b 1
