#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="/var/lib/stealth-core"
STATE_FILE="$STATE_DIR/setup.env"
SYSCTL_FILE="/etc/sysctl.d/99-stealth-core.conf"
SYSCTL_BACKUP="$STATE_DIR/sysctl.backup"
WARP_PORT=40000
MODE="full"
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: setup.sh [--minimal|--full] [--dry-run]

  --minimal  Install Python TLS/network dependencies only.
  --full     Install WARP, browser dependencies and Camoufox (default).
  --dry-run  Print every action without changing the host.
EOF
}

for arg in "$@"; do
  case "$arg" in
    --minimal) MODE=minimal ;;
    --full) MODE=full ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

log() { printf '[stealth-core] %s\n' "$*"; }
run() {
  if (( DRY_RUN )); then
    printf '+ '; printf '%q ' "$@"; printf '\n'
  else
    "$@"
  fi
}

if (( !DRY_RUN )); then
  [[ "$(id -u)" -eq 0 ]] || { echo 'Run as root (or use --dry-run).' >&2; exit 1; }
fi

. /etc/os-release 2>/dev/null || true
if [[ "${ID:-}" != ubuntu && "${ID:-}" != debian && "${ID_LIKE:-}" != *debian* ]]; then
  echo 'Supported platforms: Debian and Ubuntu.' >&2
  exit 1
fi

mkdir_state() { run install -d -m 0750 "$STATE_DIR"; }

install_system_packages() {
  run apt-get update
  local packages=(ca-certificates curl gnupg python3 python3-venv python3-pip iproute2 procps)
  if [[ "$MODE" == full ]]; then
    packages+=(libgtk-3-0 libgbm1 libasound2 libxdamage1 libxfixes3 libxkbcommon0 libnss3 libxcomposite1 libxrandr2)
  fi
  run env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${packages[@]}"
}

install_warp() {
  local arch keyring listfile
  arch="$(dpkg --print-architecture)"
  keyring=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
  listfile=/etc/apt/sources.list.d/cloudflare-client.list
  run install -d -m 0755 /usr/share/keyrings
  if (( DRY_RUN )); then
    log "would download and verify Cloudflare WARP key for architecture $arch"
  else
    curl --fail --silent --show-error --location https://pkg.cloudflareclient.com/pubkey.gpg | gpg --dearmor --yes -o "$keyring"
  fi
  run bash -c "printf '%s\\n' 'deb [arch=$arch signed-by=$keyring] https://pkg.cloudflareclient.com/ stable main' > '$listfile'"
  run apt-get update
  run env DEBIAN_FRONTEND=noninteractive apt-get install -y cloudflare-warp
  if (( !DRY_RUN )); then
    if ! warp-cli --accept-tos account 2>/dev/null | grep -q 'Account type'; then
      run warp-cli --accept-tos registration new
    fi
  fi
  run warp-cli --accept-tos mode proxy
  run warp-cli --accept-tos proxy port "$WARP_PORT"
  run warp-cli --accept-tos connect
}

configure_sysctl() {
  mkdir_state
  if (( DRY_RUN )); then
    log "would back up current net.ipv4.ip_default_ttl and write $SYSCTL_FILE"
  else
    if [[ ! -e "$SYSCTL_BACKUP" ]]; then
      current="$(sysctl -n net.ipv4.ip_default_ttl)"
      printf 'net.ipv4.ip_default_ttl=%s\n' "$current" > "$SYSCTL_BACKUP"
      chmod 0600 "$SYSCTL_BACKUP"
    fi
  fi
  run install -D -m 0644 /dev/null "$SYSCTL_FILE"
  run bash -c "printf '%s\\n' 'net.ipv4.ip_default_ttl=64' > '$SYSCTL_FILE'"
  run sysctl --system
}

install_python() {
  local venv="$PROJECT_ROOT/.venv"
  run python3 -m venv "$venv"
  run "$venv/bin/python" -m pip install --upgrade pip wheel
  run "$venv/bin/python" -m pip install 'curl-cffi>=0.7,<1' 'httpx>=0.27,<1'
  if [[ "$MODE" == full ]]; then
    run "$venv/bin/python" -m pip install 'camoufox>=0.4,<1' 'pytest>=8,<9'
    run "$venv/bin/python" -m camoufox fetch
  else
    run "$venv/bin/python" -m pip install 'pytest>=8,<9'
  fi
  if [[ -f "$PROJECT_ROOT/pyproject.toml" ]]; then
    run "$venv/bin/python" -m pip install -e "$PROJECT_ROOT"
  fi
}

verify_install() {
  if (( DRY_RUN )); then return; fi
  "$PROJECT_ROOT/.venv/bin/python" - <<'PY'
from stealth_core.network import Socks5hProxy
from stealth_core.tls_client import TLSClient
assert Socks5hProxy().url == "socks5h://127.0.0.1:40000"
print("stealth-core Python import check: OK")
PY
  if [[ "$MODE" == full ]]; then
    warp-cli --accept-tos status
  fi
}

log "install mode: $MODE"
install_system_packages
if [[ "$MODE" == full ]]; then install_warp; fi
configure_sysctl
install_python
verify_install
if (( !DRY_RUN )); then
  mkdir_state
  cat > "$STATE_FILE" <<EOF
PROJECT_ROOT=$PROJECT_ROOT
MODE=$MODE
WARP_PORT=$WARP_PORT
SYSCTL_FILE=$SYSCTL_FILE
SYSCTL_BACKUP=$SYSCTL_BACKUP
EOF
  chmod 0600 "$STATE_FILE"
fi
log 'setup completed'
