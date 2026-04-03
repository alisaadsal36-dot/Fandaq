#!/bin/bash
set -e

# Use the port assigned by Railway, or default to 8000
PORT=${PORT:-8000}

echo "=== Environment Check ==="
echo "PORT=$PORT"
echo "DATABASE_URL is set: $([ -n "$DATABASE_URL" ] && echo 'YES' || echo 'NO')"
echo "OPENAI_API_KEY is set: $([ -n "$OPENAI_API_KEY" ] && echo 'YES' || echo 'NO')"
echo "WHATSAPP_API_TOKEN is set: $([ -n "$WHATSAPP_API_TOKEN" ] && echo 'YES' || echo 'NO')"
echo "TELEGRAM_BOT_TOKEN is set: $([ -n "$TELEGRAM_BOT_TOKEN" ] && echo 'YES' || echo 'NO')"
echo "========================="

# Run migrations
echo "Running migrations..."
alembic upgrade head || echo "⚠️ Migration failed, continuing anyway..."

echo "Starting Uvicorn on port $PORT..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --log-level info
