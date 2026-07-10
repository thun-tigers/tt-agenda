# Deployment Guide für TT-Agenda

## Übersicht

Diese Anleitung zeigt dir, wie du die TT-Agenda App standalone deployen kannst.

> **Hinweis:** Der reguläre Produktions-Deploy erfolgt über den zentralen Stack in `../tt-infra` (Caddy-Proxy, tt-auth, gemeinsamer Docker-Compose-Stack). Die hier beschriebenen Schritte sind für Standalone-/Entwicklungs-Deploys gedacht. Für Produktion siehe die Dokumente in `tt-infra`.

## Option 1: Lokales Docker Image (Entwicklung)

### Schnellstart
```bash
# Image bauen und starten
docker-compose up -d

# Logs anschauen
docker-compose logs -f

# Stoppen
docker-compose down
```

Siehe `README_DOCKER.md` für Details.

## Option 2: GitHub Container Registry (Produktion)

### Voraussetzungen
1. GitHub Repository mit Push-Zugriff
2. Docker auf dem Ziel-Server installiert

### Schritt 1: Docker Image in GitHub bauen

1. **Gehe zu GitHub Actions:**
   - Öffne dein Repository auf GitHub
   - Klicke auf "Actions" Tab
   - Wähle "Docker Build and Push"
   - Klicke "Run workflow"
   - Gib einen Tag ein (z.B. `v1.0.0`)
   - Klicke "Run workflow"

2. **Warte auf den Build:**
   - Der Build dauert ca. 2-5 Minuten
   - Grüner Haken = Erfolgreich
   - Bei Fehler: Klicke auf den Job für Details

### Schritt 2: Image auf Server deployen

#### A. Server vorbereiten

```bash
# Docker installieren (falls noch nicht vorhanden)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Docker Compose installieren
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

#### B. GitHub Container Registry Login

```bash
# Personal Access Token erstellen:
# GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
# Scopes: read:packages

# Login
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

#### C. Docker Compose Datei erstellen

Erstelle auf dem Server `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  web:
    image: ghcr.io/YOUR_USERNAME/tt-agenda:latest
    container_name: tt-agenda
    ports:
      - "8086:5000"
    volumes:
      - ./instance:/app/instance
      - ./backups:/app/backups
    environment:
      - FLASK_ENV=production
      - TZ=Europe/Zurich
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/login"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

#### D. Starten

```bash
# Erstmaliger Start
docker-compose -f docker-compose.prod.yml up -d

# Logs anschauen
docker-compose -f docker-compose.prod.yml logs -f

# Status prüfen
docker-compose -f docker-compose.prod.yml ps
```

### Schritt 3: Updates deployen

```bash
# 1. Neues Image in GitHub bauen (siehe Schritt 1)

# 2. Auf dem Server:
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d

# 3. Alte Images aufräumen
docker image prune -a
```

## Option 3: Reverse Proxy mit Nginx (Empfohlen für Produktion)

### Nginx installieren

```bash
sudo apt update
sudo apt install nginx
```

### Nginx konfigurieren

Erstelle `/etc/nginx/sites-available/tt-agenda`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Aktivieren

```bash
sudo ln -s /etc/nginx/sites-available/tt-agenda /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### SSL mit Let's Encrypt (Optional)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Backup & Restore

### Automatisches Backup-Script

Erstelle `backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/app/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup erstellen
docker-compose -f docker-compose.prod.yml exec -T web \
  tar -czf /app/backups/backup_$DATE.tar.gz /app/instance

# Alte Backups löschen (älter als 30 Tage)
find $BACKUP_DIR -name "backup_*.tar.gz" -mtime +30 -delete

echo "Backup erstellt: backup_$DATE.tar.gz"
```

### Cronjob für tägliches Backup

```bash
# Crontab bearbeiten
crontab -e

# Täglich um 2 Uhr morgens
0 2 * * * /path/to/backup.sh
```

### Restore

```bash
# Backup-Datei auswählen
BACKUP_FILE="backup_20240101_020000.tar.gz"

# Container stoppen
docker-compose -f docker-compose.prod.yml down

# Restore
tar -xzf backups/$BACKUP_FILE -C .

# Container starten
docker-compose -f docker-compose.prod.yml up -d
```

## Monitoring

### Logs überwachen

```bash
# Alle Logs
docker-compose -f docker-compose.prod.yml logs -f

# Nur Fehler
docker-compose -f docker-compose.prod.yml logs -f | grep -i error

# Letzte 100 Zeilen
docker-compose -f docker-compose.prod.yml logs --tail=100
```

### Health Check

```bash
# Status prüfen
curl http://localhost:5000/login

# Mit Details
docker-compose -f docker-compose.prod.yml ps
```

## Troubleshooting

### Container startet nicht

```bash
# Logs prüfen
docker-compose -f docker-compose.prod.yml logs

# Container-Status
docker ps -a

# Neustart erzwingen
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d
```

### Port bereits belegt

```bash
# Prüfen welcher Prozess den externen Port nutzt
sudo lsof -i :8086

# Port in docker-compose.prod.yml ändern
ports:
  - "8080:5000"  # Externer Port:Interner Port
```

### Datenbank-Probleme

```bash
# Backup erstellen
cp instance/trainings.db instance/trainings.db.backup

# Container stoppen
docker-compose -f docker-compose.prod.yml down

# Datenbank neu initialisieren
rm instance/trainings.db

# Container starten
docker-compose -f docker-compose.prod.yml up -d
```

## Sicherheit

### Wichtige Schritte für Produktion:

1. **Secret Key setzen**: `SECRET_KEY` als Environment-Variable im Container / in `.env` mit einem sicheren zufälligen Wert belegen. Die Konfiguration wird in `app/config.py` gelesen; `app/__init__.py` (`create_app`) baut die App über die Factory in `run.py` (`run:app`) — es existiert keine `app.py`.

2. **Debug-Modus**: Im Container läuft die App per Gunicorn ohne Debug. Debug lässt sich lokal nur explizit über `FLASK_DEBUG=true python run.py` aktivieren.

3. **Firewall konfigurieren**:
   ```bash
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```

4. **Regelmäßige Updates**:
   ```bash
   # System-Updates
   sudo apt update && sudo apt upgrade
   
   # Docker-Updates
   docker-compose -f docker-compose.prod.yml pull
   docker-compose -f docker-compose.prod.yml up -d
   ```

## Performance-Optimierung

### WSGI-Server (Gunicorn)

Gunicorn ist bereits im `Dockerfile`-`CMD` konfiguriert und in `requirements.txt` gepinnt (`gunicorn --bind 0.0.0.0:5000 --workers 1 --timeout 120 run:app`). Für höhere Last kann die Worker-Zahl im Dockerfile erhöht oder über eine `docker-compose.override.yml` per `command:` überschrieben werden.

## Support

Bei Problemen:
1. Prüfe die Logs: `docker-compose logs -f`
2. Prüfe den Health Check: `curl http://localhost:8086/login` (bzw. den in `docker-compose.yml` gemappten externen Port)
3. Siehe `README_DOCKER.md` für weitere Details
4. Siehe `.github/workflows/README.md` für GitHub Actions Hilfe
5. Für den regulären Produktionsbetrieb siehe `../tt-infra`.
