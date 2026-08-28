#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
HERMES_SKILL_DIR="${HERMES_HOME:-$HOME/.hermes}/skills/razor"

echo "======================================================"
echo " [RAZOR] Auto-Update & Synchronizer                  "
echo "======================================================"

# 1. Безопасное обновление репозитория
if [ -d "$PROJECT_ROOT/.git" ]; then
    echo "[1/4] Checking repository status..."
    cd "$PROJECT_ROOT"
    
    # Проверка на наличие незакоммиченных изменений
    if [ -n "$(git status --porcelain)" ]; then
        echo "  [!] Working tree contains uncommitted changes. Skipping git pull to preserve local modifications."
    else
        echo "  [*] Pulling latest changes (fast-forward only)..."
        git pull --ff-only origin main --quiet || {
            echo "  [!] Fast-forward pull failed. Please resolve branches manually."
        }
        echo "  ✓ Repository synced to $(git rev-parse --short HEAD)"
    fi
else
    echo "[1/4] Non-git environment. Skipping git sync."
fi

# 2. Обновление Python-зависимостей
echo "[2/4] Verifying Python dependencies..."
if [ -n "${VIRTUAL_ENV:-}" ]; then
    pip install --upgrade --quiet curl_cffi "camoufox[geoip]" rich 2>/dev/null || true
else
    pip install --upgrade --quiet curl_cffi "camoufox[geoip]" rich --user 2>/dev/null ||     pip3 install --upgrade --quiet curl_cffi "camoufox[geoip]" rich --break-system-packages 2>/dev/null || true
fi

# 3. Синхронизация скилла в ~/.hermes/skills/razor/
echo "[3/4] Syncing SKILL.md into Hermes Agent runtime..."
mkdir -p "$HERMES_SKILL_DIR"
cp -f "$PROJECT_ROOT/SKILL.md" "$HERMES_SKILL_DIR/SKILL.md"
echo "  ✓ Synced to $HERMES_SKILL_DIR/SKILL.md"

# 4. Прогон верификационного оракула
echo "[4/4] Running Diagnostic Preflight..."
PYTHONPATH="$PROJECT_ROOT" python3 "$SCRIPT_DIR/verify_oracle.py" || true

echo "======================================================"
echo " [RAZOR] Update check completed successfully!        "
echo "======================================================"
