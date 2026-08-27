@echo off
REM ===========================================================================
REM TRANSCRIBE AI - Generation de dist\TranscribeAI.exe (PyInstaller)
REM ===========================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Environnement introuvable. Executez d'abord install.bat
    pause
    exit /b 1
)

echo [1/3] Installation des outils de build...
call .venv\Scripts\python.exe -m pip install -r requirements-dev.txt

echo [2/3] Nettoyage des artefacts precedents...
if exist "build" rmdir /s /q "build"
if exist "dist"  rmdir /s /q "dist"

echo [3/3] Compilation...
call .venv\Scripts\python.exe -m PyInstaller TranscribeAI.spec --noconfirm --clean
if errorlevel 1 (
    echo ERREUR: la compilation a echoue.
    pause
    exit /b 1
)

echo.
echo Executable genere : dist\TranscribeAI.exe
pause
