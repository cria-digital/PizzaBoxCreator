#!/usr/bin/env bash
# Manual database backup script.
# Usage: ./scripts/backup.sh [output_dir]
# Requires: pg_dump (from postgresql-client), gzip
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${1:-$PROJECT_DIR/storage/backups}"

# Source DATABASE_URL from .env if running outside Docker.
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

DATABASE_URL="${DATABASE_URL:-sqlite:///storage/pizzabox.db}"
mkdir -p "$OUTPUT_DIR"

if [[ "$DATABASE_URL" == sqlite* ]]; then
    # SQLite backup
    DB_PATH="${DATABASE_URL#sqlite:///}"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    OUTFILE="$OUTPUT_DIR/pizzabox_${TIMESTAMP}.db"
    cp "$DB_PATH" "$OUTFILE"
    gzip "$OUTFILE"
    echo "SQLite backup: ${OUTFILE}.gz"
else
    # PostgreSQL backup — extract connection details from DATABASE_URL
    # Format: postgresql://user:pass@host:port/dbname
    URI="${DATABASE_URL#postgresql://}"
    DB_USER="${URI%%:*}"
    REST="${URI#*:}"
    DB_PASS="${REST%%@*}"
    REST="${REST#*@}"
    DB_HOST="${REST%%:*}"
    REST="${REST#*:}"
    DB_PORT="${REST%%/*}"
    DB_NAME="${REST#*/}"

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    OUTFILE="$OUTPUT_DIR/pizzabox_${TIMESTAMP}.sql.gz"

    PGPASSWORD="$DB_PASS" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME" \
        | gzip > "$OUTFILE"

    echo "PostgreSQL backup: $OUTFILE"
fi

# Keep last 30 backups
ls -1t "$OUTPUT_DIR"/pizzabox_*.sql.gz "$OUTPUT_DIR"/pizzabox_*.db.gz 2>/dev/null \
    | tail -n +31 | xargs -r rm
