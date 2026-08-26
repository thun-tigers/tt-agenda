# Docker Deployment für TT-Agenda

## Voraussetzungen
- Docker installiert
- Docker Compose installiert (optional, aber empfohlen)

## Schnellstart

### Mit Docker Compose (empfohlen)

1. **Image bauen und Container starten:**
   ```bash
   docker-compose up -d
   ```

2. **Anwendung öffnen:**
   - Öffne Browser: http://localhost:8086
   - Der Login erfolgt zentral über tt-auth (SSO). Es gibt keine lokalen Default-Zugangsdaten mehr; `AUTH_BASE_URL` muss auf eine erreichbare tt-auth Instanz zeigen.

3. **Logs anzeigen:**
   ```bash
   docker-compose logs -f
   ```

4. **Container stoppen:**
   ```bash
   docker-compose down
   ```

### Mit Docker (ohne Compose)

1. **Image bauen:**
   ```bash
   docker build -t tt-agenda .
   ```

2. **Container starten:**
   ```bash
   docker run -d \
     --name tt-agenda \
     -p 8086:5000 \
     -v $(pwd)/instance:/app/instance \
     tt-agenda
   ```

   Der Container lauscht intern auf Port `5000` (Gunicorn); nach aussen wird `8086` gemappt — analog zur `docker-compose.yml`.

3. **Container stoppen:**
   ```bash
   docker stop tt-agenda
   docker rm tt-agenda
   ```

## Wichtige Befehle

### Container-Status prüfen
```bash
docker-compose ps
```

### In den Container einsteigen
```bash
docker-compose exec web bash
```

### Logs anzeigen
```bash
docker-compose logs -f web
```

### Container neu starten
```bash
docker-compose restart
```

### Image neu bauen (nach Code-Änderungen)
```bash
docker-compose up -d --build
```

## Datenbank

Die App ist für PostgreSQL ausgelegt. Im Tigers-Stack übernimmt `tt-postgres-agenda` die Persistenz, lokal kann die DB über die Compose-Datei mitgestartet werden.

### Datenbank-Reset
```bash
docker-compose down -v
docker-compose up -d
```

## Produktion

Die App verwendet die Flask App Factory `create_app` aus `app/__init__.py`; der Einstiegspunkt ist `run.py` (`run:app`). Es gibt keine `app.py`.

### Wichtige Sicherheitshinweise

1. **Secret Key setzen:** `SECRET_KEY` in `.env` bzw. als Container-Env-Variable auf einen sicheren zufälligen Wert setzen.

2. **Debug-Modus:** Debug wird per `FLASK_DEBUG` gesteuert und ist im Container standardmässig aus (Gunicorn statt Flask-Devserver).

3. **WSGI-Server:** Gunicorn ist bereits im Dockerfile-`CMD` konfiguriert (`gunicorn --bind 0.0.0.0:5000 --workers 1 --timeout 120 run:app`) und in `requirements.txt` gepinnt — keine weiteren Anpassungen nötig.

### Port ändern
Der Container lauscht intern immer auf `5000`. Um einen anderen externen Port zu verwenden, in `docker-compose.yml` ändern:
```yaml
ports:
  - "8080:5000"  # Externer Port:Interner Port
```

## Troubleshooting

### Container startet nicht
```bash
docker-compose logs web
```

### Port bereits belegt
Ändere den externen Port in `docker-compose.yml` oder stoppe den anderen Service:
```bash
lsof -i :8086
```

### Datenbank-Probleme
```bash
# Container stoppen
docker-compose down

# Datenbank löschen
rm -rf instance/

# Neu starten
docker-compose up -d
```

### Änderungen werden nicht übernommen
```bash
# Image neu bauen
docker-compose build --no-cache
docker-compose up -d
```

## Netzwerk-Zugriff

### Zugriff von anderen Geräten im Netzwerk
1. Finde deine IP-Adresse:
   ```bash
   # macOS/Linux
   ifconfig | grep "inet "
   
   # Windows
   ipconfig
   ```

2. Öffne im Browser: `http://DEINE-IP:8086`

### Firewall-Einstellungen
Stelle sicher, dass Port 8086 (bzw. der in `docker-compose.yml` gemappte externe Port) in deiner Firewall geöffnet ist.

## Updates

### Code aktualisieren
```bash
git pull
docker-compose up -d --build
```

### Dependencies aktualisieren
```bash
# requirements.txt bearbeiten
docker-compose build --no-cache
docker-compose up -d
```

## Backup & Restore

### Komplettes Backup
```bash
# Backup erstellen
tar -czf tt-agenda-backup-$(date +%Y%m%d).tar.gz instance/

# Backup wiederherstellen
Der zentrale Restore läuft über `tt-infra` und nicht über die Agenda-App direkt.
```

## Support

Bei Problemen:
1. Prüfe die Logs: `docker-compose logs -f`
2. Prüfe den Container-Status: `docker-compose ps`
3. Prüfe die Datenbank: `ls -la instance/`
