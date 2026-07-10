# Production Stage - Python Anwendung
FROM python:3.12-slim

# Setze Arbeitsverzeichnis
WORKDIR /app

# Installiere System-Dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Kopiere Requirements
COPY requirements.txt .

# Installiere Python-Dependencies
ARG TT_COMMON_REF=v0.1.17
RUN sed -i "s#@v[0-9][0-9.]*#@${TT_COMMON_REF}#" requirements.txt \
    && pip install --no-cache-dir -r requirements.txt

# Kopiere Anwendungscode
COPY . .

# Erstelle Verzeichnis für die Datenbank
RUN mkdir -p /app/instance

# Non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup --no-create-home appuser \
    && chown -R appuser:appgroup /app
USER appuser

# Setze Umgebungsvariablen
ENV FLASK_APP=run.py
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Zurich

# Exponiere Port 5000
EXPOSE 5000

# Starte die Anwendung
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "run:app"]
