#!/bin/bash

# Farben für die Ausgabe
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Wave Visualizer Setup Script${NC}"
echo "================================"

# Prüfen ob Python3 installiert ist
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python3 ist nicht installiert. Installation wird gestartet...${NC}"
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv
fi

# Prüfen ob FFmpeg installiert ist
if ! command -v ffmpeg &> /dev/null; then
    echo -e "${RED}FFmpeg ist nicht installiert. Installation wird gestartet...${NC}"
    sudo apt-get update
    sudo apt-get install -y ffmpeg
fi

# Virtuelle Umgebung erstellen
echo -e "${GREEN}Erstelle virtuelle Umgebung...${NC}"
python3 -m venv venv
source venv/bin/activate

# Abhängigkeiten installieren
echo -e "${GREEN}Installiere Python-Abhängigkeiten...${NC}"
pip install -r requirements.txt

# Verzeichnisse erstellen
echo -e "${GREEN}Erstelle notwendige Verzeichnisse...${NC}"
mkdir -p uploads output
chmod 755 uploads output

# ngrok installieren (optional)
read -p "Möchten Sie ngrok installieren? (j/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Jj]$ ]]; then
    echo -e "${GREEN}Installiere ngrok...${NC}"
    if ! command -v snap &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y snapd
    fi
    sudo snap install ngrok
    
    echo -e "${GREEN}ngrok wurde installiert. Bitte konfigurieren Sie es mit:${NC}"
    echo "ngrok config add-authtoken [Ihr-Token]"
fi

echo -e "${GREEN}Setup abgeschlossen!${NC}"
echo "Um die Anwendung zu starten:"
echo "1. Virtuelle Umgebung aktivieren: source venv/bin/activate"
echo "2. Anwendung starten: gunicorn -w 4 -b 0.0.0.0:5000 app:app"
echo "3. Optional: ngrok starten: ngrok http 5000" 