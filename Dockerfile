# ── Stage 1: Build Svelte frontend ──────────────────────────────────
FROM node:22-slim AS frontend-build
WORKDIR /build/frontend

COPY frontend/package.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build


# ── Stage 2: Final image — hotio/base (Alpine) ───────────────────────
FROM ghcr.io/hotio/base:alpinevpn

# Install Python 3; all deps have musllinux wheels so no build toolchain needed
COPY requirements.txt /tmp/requirements.txt
RUN apk add --no-cache python3 \
    && python3 -m venv /app/.venv \
    && /app/.venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Copy application code
WORKDIR /app
COPY main.py ./
COPY app/ ./app/

# Copy compiled frontend assets (served in a later milestone)
COPY --from=frontend-build /build/frontend/build ./frontend/build

# Overlay s6 service definitions and any root filesystem additions
COPY root/ /

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_PORT=8012

EXPOSE 8012
