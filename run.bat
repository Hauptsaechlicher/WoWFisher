@echo off
cd /d "%~dp0"

REM Prüfen ob .venv existiert
if exist ".venv\Scripts\python.exe" (
    echo Starte Bot mit lokaler .venv Umgebung...
    ".venv\Scripts\python.exe" src\gui.py
) else (
    echo Keine .venv gefunden, versuche globales Python...
    python src\gui.py
)

if %errorlevel% neq 0 (
    echo Ein Fehler ist aufgetreten!
    pause
)