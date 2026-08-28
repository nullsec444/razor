#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="/var/lib/stealth-core"
STATE_FILE="$STATE_DIR/setup.env"
SYSCTL_FILE="/etc/sysctl.d/99-stealth-core.conf"
SYSCTL_BACKUP="$STATE_DIR/sysctl.backup"
DRY_RUN=0
PURGE=0

usage() { echo 'Usage: uninstall.sh [--purge] [--dry-run]'; }
for arg in "$@"; do
  case "$arg" in
    --purge) PURGE=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $arg" >&2; usage >&2; exit 2 ;;
  esac
done
run() {
  if (( DRY_RUN )); then printf '+ '; printf '%q ' "$@"; printf '\n'; else "$@"; fi
}
if (( !DRY_RUN )); then [[ "$(id -u)" -eq 0 ]] || { echo 'Run as root (or use --dry-run).' >&2; exit 1; }; fi

if command -v warp-cli >/dev/null 2>&1; then
  run warp-cli --accept-tos disconnect || true
  run warp-cli --accept-tos mode off || true
fi

if [[ -f "$SYSCTL_BACKUP" ]]; then
  original="$(sed -n 's/^net\.ipv4\.ip_default_ttl=//p' "$SYSCTL_BACKUP" | head -n1)"
  if [[ "$original" =~ ^[0-9]+$ ]]; then run sysctl -w "net.ipv4.ip_default_ttl=$original"; fi
fi
run rm -f "$SYSCTL_FILE"
run sysctl --system
run rm -f "$SYSCTL_BACKUP"

if (( PURGE )); then
  run rm -rf "$PROJECT_ROOT/.venv"
  if command -v apt-get >/dev/null 2>&1; then
    run env DEBIAN_FRONTEND=noninteractive apt-get purge -y cloudflare-warp || true
    run apt-get autoremove -y || true
  fi
  run rm -f /etc/apt/sources.list.d/cloudflare-client.list /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
fi
run rm -f "$STATE_FILE"
run rmdir "$STATE_DIR" 2>/dev/null || true
echo 'stealth-core uninstall completed'
