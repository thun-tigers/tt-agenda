FROM node:22-alpine AS frontend

WORKDIR /frontend

COPY package.json package-lock.json ./
RUN npm ci

COPY tailwind.config.js postcss.config.js ./
COPY app ./app
RUN npm run build:css

FROM python:3.12-slim

WORKDIR /app

# postgresql-client-16 exakt passend zur Server-Version (postgres:16-alpine in compose.yml) via PGDG-Repo,
# da Debian trixie standardmaessig nur Client v17 anbietet (inkompatible SET-Parameter bei Dump/Restore).
RUN apt-get update && apt-get install -y gcc curl ca-certificates gnupg lsb-release \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main 16" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y postgresql-client-16 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend /frontend/app/static/css/tailwind.generated.css /app/app/static/css/tailwind.generated.css

RUN mkdir -p /app/instance

RUN addgroup --system appgroup && adduser --system --ingroup appgroup --no-create-home appuser \
    && chown -R appuser:appgroup /app
USER appuser

ENV FLASK_APP=run.py
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Zurich

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "run:app"]
