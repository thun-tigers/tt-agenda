# PWA (Progressive Web App) Setup

Die TT-Agenda ist jetzt als Progressive Web App konfiguriert!

## ✨ Was ist eine PWA?

Eine PWA verhält sich wie eine native App, läuft aber im Browser:

- **Installierbar** auf Smartphone und Desktop
- **Offline-Funktionalität** durch Service Worker
- **App-Icon** auf dem Homescreen
- **Vollbild-Modus** ohne Browser-UI
- **Push-Benachrichtigungen** (optional)

## 🚀 Features

✅ **Web App Manifest** - App-Metadaten und Icons
✅ **Service Worker** - Caching für Offline-Nutzung
✅ **Wake Lock** - Bildschirm bleibt in Live-Ansicht an
✅ **Responsive Design** - Optimiert für alle Bildschirmgrößen
✅ **Dark Mode** - Automatisches Theme-Switching

## 📱 Installation

### Auf Android (Chrome/Edge)

1. Öffne die App im Browser
2. Klicke auf Menü (⋮) → "App installieren" oder "Zum Startbildschirm hinzufügen"
3. Die App erscheint auf deinem Homescreen

### Auf iOS (Safari)

1. Öffne die App in Safari
2. Tippe auf das Teilen-Symbol (↑)
3. Scrolle und wähle "Zum Home-Bildschirm"
4. Bestätige mit "Hinzufügen"

### Auf Desktop (Chrome/Edge)

1. Öffne die App im Browser
2. Klicke auf das (+) Symbol in der Adressleiste
3. Oder: Menü → "App installieren..."

## 🔧 Konfiguration

### Icons erstellen

Die App benötigt Icons in verschiedenen Größen. Platziere sie in `app/static/icons/`:

``` txt
app/static/icons/
├── icon-72x72.png
├── icon-96x96.png
├── icon-128x128.png
├── icon-144x144.png
├── icon-152x152.png
├── icon-192x192.png
├── icon-384x384.png
└── icon-512x512.png
```

**Icon-Generator Tools:**

- <https://www.pwabuilder.com/imageGenerator>
- <https://realfavicongenerator.net/>

### Manifest anpassen

Bearbeite `app/static/manifest.json`:

```json
{
  "name": "Tigers Trainingsverwaltung",
  "short_name": "TT-Agenda",
  "theme_color": "#4f46e5",
  "background_color": "#1e293b",
  ...
}
```

### Service Worker Cache-Strategie

Der Service Worker in `app/static/service-worker.js` nutzt:

- **Network First** für `/live` und API-Calls (immer aktuell)
- **Cache First** für statische Ressourcen (schneller)

**Cache leeren:**

```javascript
// In Browser DevTools Console:
caches.keys().then(keys => keys.forEach(key => caches.delete(key)))
```

## 🧪 Testen

### Lokal testen

```bash
flask run --host=0.0.0.0 --port=3000
```

Öffne: `http://localhost:3000`

### PWA-Kriterien prüfen

**Chrome DevTools:**

1. F12 → Tab "Lighthouse"
2. Wähle "Progressive Web App"
3. Klicke "Analyze page load"

**Oder manuell:**

1. F12 → Tab "Application"
2. Links: "Manifest" prüfen
3. Links: "Service Workers" prüfen
4. Cache Storage ansehen

## 📋 PWA-Checkliste

- [x] `manifest.json` erstellt
- [x] Service Worker registriert
- [x] HTTPS in Production (erforderlich!)
- [ ] Icons in allen Größen erstellt
- [x] Meta-Tags für iOS hinzugefügt
- [x] Responsive Design
- [x] Offline-Fallback

## ⚠️ Wichtige Hinweise

### HTTPS erforderlich

Service Worker funktionieren nur über HTTPS (außer localhost).
Dein Server muss SSL/TLS konfiguriert haben.

### Browser-Unterstützung

- ✅ Chrome/Edge Android: Vollständig
- ✅ Safari iOS 16.4+: Vollständig
- ✅ Firefox Android: Größtenteils
- ⚠️ Safari iOS < 16.4: Eingeschränkt

### Cache-Updates

Nach Code-Änderungen:

1. Service Worker Version in `service-worker.js` ändern:

   ```javascript
   const CACHE_NAME = 'tt-agenda-v2'; // Version erhöhen
   ```

2. User müssen die App neu laden (oder sie lädt automatisch beim nächsten Besuch)

## 🔄 Updates deployen

Nach Änderungen am Service Worker:

```bash
# Service Worker Cache-Version erhöhen
sed -i "s/tt-agenda-v1/tt-agenda-v2/" app/static/service-worker.js

# Deployen
git add .
git commit -m "Update PWA cache version"
git push
```

## 📊 Analytics (optional)

PWA-Installationen tracken:

```javascript
window.addEventListener('appinstalled', () => {
  console.log('PWA wurde installiert');
  // Analytics-Event senden
});
```

## 🐛 Troubleshooting

**Problem:** App wird nicht als installierbar erkannt

- Lösung: Prüfe manifest.json und Icons
- Chrome DevTools → Application → Manifest

**Problem:** Service Worker registriert nicht

- Lösung: Prüfe Console auf Fehler
- Stelle sicher, dass HTTPS aktiv ist

**Problem:** Alte Version wird gecacht

- Lösung: Cache leeren oder Version erhöhen

**Problem:** Icons werden nicht angezeigt

- Lösung: Prüfe Pfade in manifest.json
- Icons müssen über HTTP erreichbar sein

## 📚 Weitere Ressourcen

- [MDN: Progressive Web Apps](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps)
- [web.dev: PWA](https://web.dev/progressive-web-apps/)
- [PWABuilder](https://www.pwabuilder.com/)
