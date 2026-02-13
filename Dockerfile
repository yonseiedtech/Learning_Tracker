FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libreoffice-core \
    libreoffice-impress \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

ENV PORT=8080

CMD exec gunicorn --bind :$PORT --worker-class eventlet -w 1 main:app
