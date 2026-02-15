#!/usr/bin/env bash
set -euo pipefail

# Epstein Files — Deployment script for vani3
# Usage: bash deploy/deploy.sh

PROJECT_DIR="/root/epstein"
cd "$PROJECT_DIR"

echo "=== Pulling latest code ==="
git pull origin main 2>/dev/null || echo "(not a git repo, skipping pull)"

echo "=== Installing Python dependencies ==="
.venv/bin/pip install -r api/requirements.txt --quiet

echo "=== Building FTS index ==="
.venv/bin/python -m api.search --init --populate

echo "=== Building ChromaDB (RAG) ==="
.venv/bin/python -m api.ingest

echo "=== Building Next.js frontend ==="
cd web
npm ci --production=false
NEXT_PUBLIC_API_URL=https://epsteindata.cc npm run build

# Copy static files into standalone for serving
cp -r public .next/standalone/public 2>/dev/null || true
cp -r .next/static .next/standalone/.next/static
cd "$PROJECT_DIR"

echo "=== Installing systemd services ==="
cp deploy/epstein-api.service /etc/systemd/system/
cp deploy/epstein-web.service /etc/systemd/system/
systemctl daemon-reload

echo "=== Installing nginx config ==="
cp deploy/nginx.conf /etc/nginx/conf.d/epstein.conf
nginx -t

echo "=== Restarting services ==="
systemctl restart epstein-api
systemctl restart epstein-web
systemctl reload nginx

echo "=== Enabling services on boot ==="
systemctl enable epstein-api
systemctl enable epstein-web

echo ""
echo "=== Deployment complete ==="
echo "API: http://127.0.0.1:8000/api/health"
echo "Web: http://127.0.0.1:3000"
echo "Public: http://epsteindata.cc"
echo ""
echo "Next steps:"
echo "  certbot --nginx -d epsteindata.cc -d www.epsteindata.cc"
echo ""
echo "FTS cron (add to crontab -e):"
echo "  */15 * * * * cd /root/epstein && .venv/bin/python -m api.search --update"
