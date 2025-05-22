# Wave Visualizer

Ein Web-basierter Audio-Visualisierer, der WAV-Dateien in visuelle Wellenform-Videos umwandelt.

## Systemanforderungen

- Python 3.8 oder höher
- FFmpeg (für Audio/Video-Verarbeitung)
- Linux-Server mit mindestens 1GB RAM

## Installation

1. System-Abhängigkeiten installieren:
```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv ffmpeg
```

2. Repository klonen:
```bash
git clone [Ihr-Repository-URL]
cd WaveVisualizer
```

3. Virtuelle Umgebung erstellen und aktivieren:
```bash
python3 -m venv venv
source venv/bin/activate
```

4. Python-Abhängigkeiten installieren:
```bash
pip install -r requirements.txt
```

5. Verzeichnisse erstellen:
```bash
mkdir -p uploads output
```

## Ausführung

### 1. Direkte Ausführung mit Flask (Entwicklung)
```bash
python app.py
```

### 2. Produktionsausführung mit Gunicorn
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 3. Mit ngrok für öffentlichen Zugriff

1. ngrok installieren:
```bash
# Für Ubuntu/Debian
sudo snap install ngrok

# Oder manuell:
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar xvzf ngrok-v3-stable-linux-amd64.tgz
sudo mv ngrok /usr/local/bin
```

2. ngrok konfigurieren:
```bash
ngrok config add-authtoken [Ihr-ngrok-Token]
```

3. Anwendung starten und ngrok Tunnel erstellen:
```bash
# Terminal 1: Starten Sie die Anwendung
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# Terminal 2: Starten Sie ngrok
ngrok http 5000
```

## Verwendung

1. Öffnen Sie die Anwendung im Browser (entweder localhost:5000 oder die ngrok-URL)
2. Laden Sie eine WAV-Audiodatei hoch
3. Wählen Sie ein Hintergrundbild (JPG/PNG)
4. Wählen Sie eine Farbe für die Visualisierung
5. Klicken Sie auf "Upload" und warten Sie auf die Verarbeitung
6. Laden Sie das resultierende Video herunter

## Wichtige Hinweise

- Die maximale Upload-Größe ist auf 25MB begrenzt
- Unterstützte Audioformate: WAV
- Unterstützte Bildformate: JPG, PNG
- Stellen Sie sicher, dass die Verzeichnisse `uploads` und `output` Schreibrechte haben
- Für die Produktion sollten Sie HTTPS verwenden und entsprechende Sicherheitsmaßnahmen implementieren

## Fehlerbehebung

1. Wenn Sie Probleme mit FFmpeg haben:
```bash
sudo apt-get install -y ffmpeg
```

2. Wenn Sie Berechtigungsprobleme haben:
```bash
sudo chown -R $USER:$USER uploads output
chmod -R 755 uploads output
```

3. Wenn Sie Speicherprobleme haben:
```bash
# Überprüfen Sie den verfügbaren Speicher
df -h
# Bereinigen Sie alte Dateien
find uploads/ -type f -mtime +7 -delete
find output/ -type f -mtime +7 -delete
``` 