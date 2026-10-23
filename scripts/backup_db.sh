#!/usr/bin/env bash
# Backup scripts for the messenger database.
#
#   ./scripts/backup_db.sh pg      # Postgres (running compose stack) -> backups/*.sql
#   ./scripts/backup_db.sh sqlite  # legacy SQLite volume -> backups/*.db
set -euo pipefail

BACKUP_DIR="backups"
mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"

case "${1:-pg}" in
  pg)
    OUT="$BACKUP_DIR/messenger_pg_$STAMP.sql"
    docker compose exec -T db pg_dump -U messenger -d messenger > "$OUT"
    echo "Postgres dump written to $OUT"
    echo "Restore: docker compose exec -T db psql -U messenger -d messenger < $OUT"
    ;;
  sqlite)
    OUT="$BACKUP_DIR/messenger_sqlite_$STAMP.db"
    docker cp messenger-prj-backend-1:/data/messenger.db "$OUT"
    echo "SQLite copy written to $OUT"
    ;;
  *)
    echo "usage: $0 [pg|sqlite]" >&2
    exit 1
    ;;
esac
