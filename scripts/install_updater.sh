#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
UPDATE_SCRIPT="$SCRIPT_DIR/update.sh"
BIN_LINK="$HOME/.local/bin/stealth-update"

mkdir -p "$HOME/.local/bin"
ln -sf "$UPDATE_SCRIPT" "$BIN_LINK"

echo "[+] CLI alias installed: stealth-update (points to $UPDATE_SCRIPT)"

# Добавление в cron при желании
if [ "${1:-}" == "--cron" ]; then
    CRON_CMD="0 4 * * * bash $UPDATE_SCRIPT > /tmp/stealth-update.log 2>&1"
    (crontab -l 2>/dev/null | grep -v "stealth-core/scripts/update.sh" ; echo "$CRON_CMD") | crontab -
    echo "[+] Daily auto-update cron job configured (04:00 AM every day)"
fi
