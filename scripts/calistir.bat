@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo Sanal ortam bulunamadÄ±. Ã–nce scripts\kurulum.bat Ã§alÄ±ÅŸtÄ±rÄ±n.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python app.py
if errorlevel 1 (
    echo.
    echo Uygulama hata ile kapandÄ±.
    pause
)
