# ─── Stage 1: Build Tailwind CSS ──────────────────────────────────────────────
# FROM node:20-slim AS css-builder
FROM oven/bun:1 AS css-builder

WORKDIR /build

# COPY package.json package-lock.json ./
# RUN npm ci
COPY package.json bun.lockb ./
RUN bun install --frozen-lockfile

# Copy ALL application code so Tailwind can scan the HTML/JS for class names
COPY . .

# RUN npx @tailwindcss/cli -i ./static/input.css -o ./static/main.css --minify
RUN bunx @tailwindcss/cli -i ./static/input.css -o ./static/main.css --minify

# ─── Stage 2: Python Application ─────────────────────────────────────────────
FROM python:3.14-slim

# Prevent Python from writing .pyc files and enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies for psycopg (PostgreSQL) and Pillow (images)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libwebp-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy compiled CSS from builder stage (overwrite dev version)
COPY --from=css-builder /build/static/main.css ./static/main.css

# Create upload directory for media files (will be mounted as volume)
RUN mkdir -p /app/upload

# Copy and set permissions for entrypoint
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose port 8000
EXPOSE 8000

# Run entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]
