#!/bin/bash

# In das Verzeichnis des Skripts wechseln
cd "$(dirname "$0")"

# Pfad zum Python-Interpreter in der .venv
VENV_PYTHON=".venv/bin/python3"

# Prüfen, ob die .venv existiert und ausführbar ist
if [ -f "$VENV_PYTHON" ]; then
    echo "Starte Bot mit lokaler .venv Umgebung..."
    PYTHON_CMD="$VENV_PYTHON"
else
    echo "Keine .venv gefunden, versuche globales Python..."
    PYTHON_CMD="python3"
fi

# GUI starten
# "||" sorgt dafür, dass das Terminal nur offen bleibt, wenn ein Fehler passiert
$PYTHON_CMD src/gui.py || { echo "Ein Fehler ist aufgetreten! Drücke Enter zum Beenden..."; read; }