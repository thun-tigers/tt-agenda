# GitHub Actions - Manual Docker Image Build

## Übersicht

Der Workflow `manual-docker-build.yml` baut auf Anfrage ein Docker Image und
veröffentlicht es in der GitHub Container Registry (ghcr.io). Es gibt keinen
automatischen Trigger (kein Build bei jedem Push) – der Build muss bewusst
gestartet werden.

## Workflow starten

### Über GitHub UI

1. Repository auf GitHub öffnen → Tab **"Actions"**
2. Workflow **"Manual Docker Image Build"** auswählen
3. **"Run workflow"** klicken
4. Branch wählen (z. B. `main`) und einen Tag eingeben (z. B. `v1.0.0`, `latest`, `dev`)
5. **"Run workflow"** bestätigen

### Über GitHub CLI

```bash
gh auth login
gh workflow run "Manual Docker Image Build" \
  --ref main \
  -f tag=v1.0.0
```

## Image verwenden

### Login bei GHCR

```bash
# Personal Access Token mit Scope "read:packages" erstellen:
# GitHub → Settings → Developer settings → Personal access tokens
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

### Image pullen und starten

```bash
docker pull ghcr.io/thun-tigers/tt-agenda:v1.0.0
docker run -d --name tt-agenda -p 8080:5000 ghcr.io/thun-tigers/tt-agenda:v1.0.0
```

## Image-Sichtbarkeit einstellen

Standardmässig sind GHCR-Images privat. Öffentlich machen:
Repository → **Packages** → Package auswählen → **Package settings** →
**Danger Zone** → **Change visibility**.

## Voraussetzungen im Repository

Repository → Settings → Actions → General → **Workflow permissions**:
**"Read and write permissions"** (nötig, damit der Workflow nach ghcr.io pushen darf).

## Plattformen

Das Image wird für `linux/amd64` und `linux/arm64` gebaut.

## Troubleshooting

| Problem | Lösung |
| --- | --- |
| "Permission denied" beim Push | Workflow-Permissions wie oben prüfen |
| Image nicht sichtbar/pullbar | Package-Sichtbarkeit prüfen, `docker login ghcr.io` erneut ausführen |
| Build schlägt fehl | Logs im Actions-Tab prüfen, lokal testen: `docker build -t test .` |

## Weitere Informationen

- [GitHub Container Registry Dokumentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Docker Build Push Action](https://github.com/docker/build-push-action)
