@echo off
REM ===========================================================================
REM TRANSCRIBE AI - Lancement de l'application
REM ===========================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Environnement introuvable. Executez d'abord install.bat
    pause
    exit /b 1
)

call .venv\Scripts\python.exe -m transcribe_ai.main %*
if errorlevel 1 pause
