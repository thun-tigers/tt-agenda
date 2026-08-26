# GitHub Actions - Docker Build

## Übersicht

Diese GitHub Action baut automatisch ein Docker Image und speichert es in der GitHub Container Registry (ghcr.io).

## Manueller Trigger

### Über GitHub UI:

1. Gehe zu deinem Repository auf GitHub
2. Klicke auf **"Actions"** Tab
3. Wähle **"Docker Build and Push"** aus der Liste
4. Klicke auf **"Run workflow"** (rechts)
5. Wähle den Branch (z.B. `main`)
6. Gib einen Tag ein (z.B. `v1.0.0`, `latest`, `dev`)
7. Klicke auf **"Run workflow"**

### Über GitHub CLI:

```bash
# Installiere GitHub CLI (falls noch nicht installiert)
brew install gh

# Login
gh auth login

# Workflow manuell triggern
gh workflow run "Docker Build and Push" \
  --ref main \
  -f tag=v1.0.0
```

## Image verwenden

### 1. Login bei GitHub Container Registry

```bash
# Personal Access Token erstellen:
# GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
# Scope: read:packages

echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

### 2. Image pullen

```bash
# Ersetze USERNAME und REPO mit deinen Werten
docker pull ghcr.io/USERNAME/REPO:latest

# Oder mit spezifischem Tag
docker pull ghcr.io/USERNAME/REPO:v1.0.0
```

### 3. Container starten

```bash
docker run -d \
  --name tt-agenda \
  -p 5000:5000 \
  -v $(pwd)/instance:/app/instance \
  ghcr.io/USERNAME/REPO:latest
```

### 4. Mit Docker Compose

Erstelle eine `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  web:
    image: ghcr.io/USERNAME/REPO:latest
    container_name: tt-agenda
    ports:
      - "5000:5000"
    volumes:
      - ./instance:/app/instance
    environment:
      - FLASK_ENV=production
    restart: unless-stopped
```

Dann starten:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Image-Sichtbarkeit einstellen

Standardmäßig sind Images privat. Um sie öffentlich zu machen:

1. Gehe zu deinem Repository auf GitHub
2. Klicke rechts auf **"Packages"**
3. Wähle dein Package aus
4. Klicke auf **"Package settings"**
5. Scrolle zu **"Danger Zone"**
6. Klicke auf **"Change visibility"**
7. Wähle **"Public"** oder **"Private"**

## Automatischer Build (Optional)

Um den Build automatisch bei jedem Push auf `main` zu triggern, entferne die Kommentare in `.github/workflows/docker-build.yml`:

```yaml
on:
  workflow_dispatch:
    # ...
  
  push:  # ← Entferne Kommentar
    branches:
      - main
    tags:
      - 'v*'
```

## Tags

Die Action erstellt automatisch mehrere Tags:

- **Manueller Input**: Der von dir eingegebene Tag (z.B. `v1.0.0`)
- **Branch**: Der Branch-Name (z.B. `main`)
- **SHA**: Git Commit SHA (z.B. `main-abc1234`)

## Multi-Platform Support

Das Image wird für folgende Plattformen gebaut:
- `linux/amd64` (Intel/AMD CPUs)
- `linux/arm64` (ARM CPUs, z.B. Apple Silicon, Raspberry Pi)

## Troubleshooting

### "Permission denied" beim Pushen

Stelle sicher, dass die Action die richtigen Permissions hat:
- Repository → Settings → Actions → General → Workflow permissions
- Wähle: **"Read and write permissions"**

### Image nicht gefunden

1. Prüfe ob der Build erfolgreich war: Actions Tab
2. Prüfe die Package-Sichtbarkeit (siehe oben)
3. Stelle sicher, dass du eingeloggt bist: `docker login ghcr.io`

### Build schlägt fehl

1. Prüfe die Logs im Actions Tab
2. Teste den Build lokal: `docker build -t test .`
3. Prüfe ob alle Dependencies in `requirements.txt` sind

## Weitere Informationen

- [GitHub Container Registry Dokumentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [GitHub Actions Dokumentation](https://docs.github.com/en/actions)
- [Docker Build Push Action](https://github.com/docker/build-push-action)
