# Optional: venv aktivieren, z. B. `source venv/bin/activate`

import os
import sys
import getpass

# Stelle sicher, dass das Projekt-Root im Python-Pfad liegt
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from app.extensions import db
from app.models import User


def main():
    benutzer_alt = input("Benutzer (alt): ").strip()
    benutzer_neu = input("Benutzer (neu, leer lassen für keine Umbenennung): ").strip()
    passwort_neu = getpass.getpass("Neues Passwort: ").strip() # Tiger-Coach!2026 oder Tiger-Admin!2026

    if not benutzer_alt:
        print("Abbruch: kein alter Benutzername angegeben.")
        return
    if not passwort_neu:
        print("Abbruch: kein Passwort angegeben.")
        return

    app = create_app()
    with app.app_context():
        user = User.query.filter_by(username=benutzer_alt).first()
        if not user:
            print(f"Kein Benutzer '{benutzer_alt}' gefunden.")
            return

        target_username = benutzer_neu or benutzer_alt
        if benutzer_neu:
            existing = User.query.filter_by(username=benutzer_neu).first()
            if existing and existing.id != user.id:
                print(f"Abbruch: Benutzername '{benutzer_neu}' existiert bereits.")
                return
            user.username = benutzer_neu
            print(f"Benutzer '{benutzer_alt}' zu '{benutzer_neu}' umbenannt.")

        user.set_password(passwort_neu)  # hash per werkzeug
        print(f"Passwort für Benutzer '{target_username}' aktualisiert.")

        db.session.commit()


if __name__ == "__main__":
    main()
