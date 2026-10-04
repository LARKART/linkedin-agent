# Lark AI LinkedIn agent — container image for 24/7 cloud scheduling.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 TZ=Africa/Lagos
WORKDIR /app

# Fonts: Poppins is shipped in fonts/; DejaVu as a safety-net fallback.
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-dejavu-core tzdata ca-certificates curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# supercronic: a cron runner designed for containers (logs to stdout, no root cron daemon).
ARG SUPERCRONIC_VERSION=v0.2.33
RUN curl -fsSL -o /usr/local/bin/supercronic \
      "https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-amd64" \
    && chmod +x /usr/local/bin/supercronic

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# state/ and drafts/ should be a mounted volume so they persist across restarts.
VOLUME ["/app/state", "/app/drafts", "/app/images", "/app/carousels", "/app/logs"]

# Runs the schedule in deploy/crontab (container-local time = TZ above).
CMD ["supercronic", "/app/deploy/crontab"]
