# Deployment

`tt-agenda` ist ein eigenständiger Flask-Service mit PostgreSQL-Datenbank. Es
gibt keine Abhängigkeit zu anderen Tigers-Services (`tt-auth`, `tt-infra`,
`tt-common` etc.) – Login erfolgt direkt über die eigene Session-Anmeldung.

## Lokal (ohne Docker)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY='lokales-geheimnis'
export DEFAULT_ADMIN_PASSWORD='ein-sicheres-passwort-mit-mindestens-12-zeichen'
python run.py
```

Die Anwendung ist danach unter <http://127.0.0.1:5006> erreichbar. Ohne
`SQLALCHEMY_DATABASE_URI`/`DATABASE_URL` wird lokal eine SQLite-Datenbank unter
`instance/tt_agenda.db` verwendet.

## Docker Compose (empfohlen)

```bash
docker compose up -d --build
```

Startet den App-Container (Gunicorn, `run:app`) und eine PostgreSQL-Datenbank.
Die Anwendung läuft danach unter <http://127.0.0.1:8080> (Port über
`AGENDA_PORT` in `.env` konfigurierbar).

Nützliche Befehle:

```bash
docker compose logs -f          # Logs anzeigen
docker compose ps                # Status prüfen
docker compose restart           # Neustart
docker compose up -d --build     # Neu bauen nach Code-Änderungen
docker compose down -v           # Stoppen inkl. Löschen der Volumes (Datenreset)
```

### Frontend-Build (Tailwind CSS)

Beim Docker-Build wird Tailwind CSS in einer separaten Node-Buildstufe aus den
Templates und Python-Dateien kompiliert; das Laufzeit-Image benötigt kein
Node.js. Für einen lokalen Build:

```bash
npm ci
npm run build:css
```

Neue dynamisch zusammengesetzte CSS-Klassen müssen in der Tailwind-Konfiguration
ergänzt oder per Safelist eingetragen werden.

## Erforderliche Umgebungsvariablen

| Variable | Zweck | Pflicht |
| --- | --- | --- |
| `SECRET_KEY` | Flask Session-Signatur | ja |
| `DEFAULT_ADMIN_PASSWORD` | Passwort des initial angelegten `admin`-Benutzers | ja (beim ersten Start) |
| `SQLALCHEMY_DATABASE_URI` / `DATABASE_URL` | Datenbankverbindung (Standard: SQLite lokal, PostgreSQL via Compose) | nein |
| `INTERNAL_API_SECRET` | Absicherung der internen API (`app/routes/api.py`) | nein, aber empfohlen |
| `PUSHOVER_TOKEN` / `PUSHOVER_USER` | Push-Benachrichtigungen aktivieren | nein |
| `AGENDA_PORT` | Extern gemappter Port bei Docker Compose (Standard `8080`) | nein |
| `POSTGRES_PASSWORD` | Passwort der PostgreSQL-Datenbank in Compose | nein (Default für lokale Entwicklung) |

## Produktions-Hinweise

- WSGI-Server: Gunicorn ist im Dockerfile-`CMD` konfiguriert
  (`gunicorn --bind 0.0.0.0:5000 --workers 1 --timeout 120 run:app`).
- Reverse Proxy (z. B. Nginx oder Caddy) terminiert TLS und leitet auf Port
  `5000` des Containers weiter.
- Backup & Restore der Datenbank erfolgt über die eingebaute Admin-Oberfläche
  (`/admin/backup`), keine manuellen Skripte nötig.

## Troubleshooting

| Problem | Lösung |
| --- | --- |
| Container startet nicht | `docker compose logs web` prüfen |
| Port bereits belegt | `AGENDA_PORT` in `.env` anpassen oder `lsof -i :8080` prüfen |
| Datenbank zurücksetzen | `docker compose down -v && docker compose up -d` |
| Änderungen nicht sichtbar | `docker compose build --no-cache && docker compose up -d` |
