# tt-agenda

Ein einfacher Single-Service für die Thun Tigers: Anmeldung, Benutzerprofile,
Team-Mitgliedschaften und Trainingsagenda in einer Anwendung.

## Prinzip

- ein Flask-Service
- eine PostgreSQL-Datenbank (SQLite funktioniert lokal ebenfalls)
- zentrale Anmeldung und Benutzerverwaltung für Thun-Tigers-Module
- gemeinsame Rollenprüfung für Benutzer und Agenda
- Modulfreigaben pro Benutzer, aktuell zusätzlich für `tt-drillbook`

Die Anwendung ist intern in drei fachliche Bereiche gegliedert:

- `identity`: Login, Konten, Rollen, Status und Modulberechtigungen
- `members`: Profilfelder und Team-Mitgliedschaften
- `agenda`: Trainings, Aktivitäten, Live-Ansicht und Administration

## Drillbook-Modul

In der Benutzerverwaltung kann das Modul **Drillbook** aktiviert werden. Zusätzlich wird eine Modulrolle vergeben:

- `viewer`
- `coach`
- `admin`

Ist Drillbook aktiviert, erscheint der Link automatisch in der Desktop- und mobilen Navigation. Beim Öffnen wird ein kurzlebiges, signiertes SSO-Token an Drillbook übergeben; dort ist keine zweite Passwortanmeldung nötig.

Für Agenda und Drillbook muss derselbe Secret gesetzt sein:

```env
SSO_SHARED_SECRET=<langer gemeinsamer Zufallswert>
DRILLBOOK_URL=https://drillbook.thun-tigers.net
```

Zum Beispiel:

```bash
openssl rand -hex 32
```

## Mobile Navigation

Die Navigation besitzt neben der Desktop-Navigation ein Hamburger-Menü für Smartphones. Damit sind Übersicht, Live, Drillbook, Administration, Profil und Logout auch im Hochformat erreichbar.

## Lokal starten

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY='lokales-geheimnis'
export DEFAULT_ADMIN_PASSWORD='ein-sicheres-passwort-mit-mindestens-12-zeichen'
export SSO_SHARED_SECRET='gemeinsames-lokales-sso-secret'
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
