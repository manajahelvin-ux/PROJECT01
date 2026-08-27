@echo off
REM ===========================================================================
REM TRANSCRIBE AI - Installation Windows
REM Cree l'environnement virtuel et installe toutes les dependances.
REM ===========================================================================
setlocal
cd /d "%~dp0"

echo [1/4] Verification de Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR: Python 3.11+ est introuvable. Installez-le depuis python.org
    pause
    exit /b 1
)

echo [2/4] Creation de l'environnement virtuel .venv...
if not exist ".venv" python -m venv .venv
if errorlevel 1 (
    echo ERREUR: creation de l'environnement virtuel impossible.
    pause
    exit /b 1
)

echo [3/4] Installation des dependances...
call .venv\Scripts\python.exe -m pip install --upgrade pip
call .venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERREUR: installation des dependances echouee.
    pause
    exit /b 1
)

echo [4/4] Preparation du fichier de configuration...
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo Fichier .env cree. Renseignez OPENROUTER_API_KEY avant utilisation.
)

echo.
echo Verification de l'environnement :
call .venv\Scripts\python.exe -m transcribe_ai.main --doctor

echo.
echo Installation terminee. Lancez run.bat pour demarrer l'application.
pause
