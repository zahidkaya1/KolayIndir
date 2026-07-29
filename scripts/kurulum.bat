@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

where py >nul 2>nul
if errorlevel 1 (
    echo Python baÅŸlatÄ±cÄ±sÄ± bulunamadÄ±. Python 3.12 kurun.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Sanal ortam oluÅŸturuluyor...
    py -3.12 -m venv .venv
    if errorlevel 1 goto :error
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto :error
pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo Kurulum tamamlandÄ±.
echo UygulamayÄ± scripts\calistir.bat ile aÃ§abilirsiniz.
pause
exit /b 0

:error
echo.
echo Kurulum sÄ±rasÄ±nda hata oluÅŸtu.
pause
exit /b 1
