# tt-agenda

Ein einfacher Single-Service für die Thun Tigers: Anmeldung, Benutzerprofile,
Team-Mitgliedschaften und Trainingsagenda in einer Anwendung.

## Prinzip

- ein Flask-Service
- eine PostgreSQL-Datenbank (SQLite funktioniert lokal ebenfalls)
- direkte Session-Anmeldung, kein SSO
- gemeinsame Rollenprüfung für Benutzer und Agenda
- keine Abhängigkeit von `tt-auth`, `tt-members`, `tt-common`, Analytics oder Attendance

Die Anwendung ist intern in drei fachliche Bereiche gegliedert:

- `identity`: Login, Konten, Rollen und Status
- `members`: Profilfelder und Team-Mitgliedschaften
- `agenda`: Trainings, Aktivitäten, Live-Ansicht und Administration

## Lokal starten

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY='lokales-geheimnis'
export DEFAULT_ADMIN_PASSWORD='ein-sicheres-passwort-mit-mindestens-12-zeichen'
# Optional: Pushover-Benachrichtigungen aktivieren
export PUSHOVER_TOKEN='dein-pushover-application-token'
export PUSHOVER_USER='deine-pushover-user-id'
python run.py
```

Danach ist die Anwendung unter <http://127.0.0.1:5006> erreichbar.

Der erste Start erzeugt standardmässig den Benutzer `admin`. Dafür muss
`DEFAULT_ADMIN_PASSWORD` gesetzt werden; ein unsicheres eingebautes
Standardpasswort gibt es nicht. Für jede echte Umgebung müssen zusätzlich
`SECRET_KEY` und bei Nutzung der internen API `INTERNAL_API_SECRET` gesetzt
werden.

## Tests

```bash
python -m pytest -q
```

## Dokumentation

Weiterführende Dokumentation liegt unter [`docs/`](docs/):

- [Deployment](docs/deployment.md) – Docker Compose, Umgebungsvariablen, Produktion, Troubleshooting
- [PWA-Setup](docs/pwa.md) – Manifest, Service Worker, Installation auf Mobilgeräten
- [Backlog](docs/backlog.md) – geplante Themen und Prioritäten
- [GHCR-Cleanup](docs/ghcr-cleanup.md) – alte Container-Image-Versionen löschen
