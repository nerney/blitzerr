# ── Stage 1: Build Svelte frontend ──────────────────────────────────
FROM node:22-slim AS frontend-build
WORKDIR /build/frontend

COPY frontend/package.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build


# ── Stage 2: Python runtime ──────────────────────────────────────────
FROM python:3.13-slim AS final

# ca-certificates required for urllib HTTPS to GitHub (not present in slim)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py ./
COPY app/ ./app/

COPY --from=frontend-build /build/frontend/build ./frontend/build

RUN mkdir -p /opt/blitzerr

EXPOSE 8012

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
