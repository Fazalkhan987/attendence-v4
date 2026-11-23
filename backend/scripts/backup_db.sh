#!/usr/bin/env bash
# Daily PostgreSQL backup. Add to cron:  0 2 * * * /path/to/backend/scripts/backup_db.sh
# Backups contain encrypted face embeddings: store them securely and keep BIOMETRIC_ENCRYPTION_KEY separately.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
DB_URL="${DATABASE_URL/postgresql+psycopg2/postgresql}"
OUT_DIR="${BACKUP_DIR:-../backups}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
mkdir -p "$OUT_DIR"
FILE="$OUT_DIR/smart_attendance_$(date +%Y%m%d_%H%M%S).sql.gz"
pg_dump "$DB_URL" | gzip > "$FILE"
chmod 600 "$FILE"
find "$OUT_DIR" -name 'smart_attendance_*.sql.gz' -mtime +"$KEEP_DAYS" -delete
echo "Backup written: $FILE"
