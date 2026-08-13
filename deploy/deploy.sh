#!/usr/bin/env bash
# =============================================================
# deploy.sh — DigitalOcean Ubuntu 22.04 droplet setup
# Run once as root on a fresh droplet, then re-run for updates
# Usage: sudo bash deploy.sh
# =============================================================
set -euo pipefail

APP_DIR="/opt/hyderabad-urban-reality"
WWW_DIR="/var/www/hyderabad-urban-reality"
REPO_URL="https://github.com/krishnateja24/HyderabadUrbanReality.git"
BRANCH="main"

# Block volume mount point for scraped project data (~500 GB)
# Format and mount the Hetzner volume before running this script:
#   mkfs.ext4 /dev/sdb
#   mkdir -p /mnt/scraped-data
#   mount /dev/sdb /mnt/scraped-data
#   echo '/dev/sdb /mnt/scraped-data ext4 defaults 0 2' >> /etc/fstab
SCRAPED_DATA_DIR="/mnt/scraped-data/scraped_projects"
DOTNET_PORT=5001
FLASK_PORT=5000

# ── 1. System packages ──────────────────────────────────────
echo "==> Installing system packages..."
apt-get update -qq
apt-get install -y --no-install-recommends \
    nginx curl git unzip wget gnupg \
    python3 python3-venv python3-pip \
    tesseract-ocr \
    dotnet-sdk-8.0

# Install Google Chrome stable (works reliably on Hetzner Ubuntu 22.04/24.04)
if ! command -v google-chrome-stable >/dev/null 2>&1; then
    echo "==> Installing Google Chrome..."
    wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    apt-get install -y /tmp/chrome.deb
    rm /tmp/chrome.deb
fi
# webdriver-manager (in requirements.txt) auto-downloads the matching chromedriver

# ── 2. Clone / pull repo ────────────────────────────────────
if [ -d "$APP_DIR/.git" ]; then
    echo "==> Pulling latest changes..."
    git -C "$APP_DIR" fetch origin
    git -C "$APP_DIR" reset --hard "origin/$BRANCH"
else
    echo "==> Cloning repository..."
    git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

# ── 3. Block volume for scraped data ────────────────────────
# Symlink scraped_projects inside the app to the block volume so data survives redeploys.
if mountpoint -q /mnt/scraped-data; then
    echo "==> Setting up scraped_projects on block volume..."
    mkdir -p "$SCRAPED_DATA_DIR"
    chown -R www-data:www-data "$SCRAPED_DATA_DIR"
    # Replace or create the symlink
    rm -rf "$APP_DIR/backend/scraped_projects"
    ln -sfn "$SCRAPED_DATA_DIR" "$APP_DIR/backend/scraped_projects"
    echo "    scraped_projects → $SCRAPED_DATA_DIR"
else
    echo "⚠  /mnt/scraped-data is not mounted. scraped_projects will use local disk."
    echo "   Mount your Hetzner volume and re-run deploy.sh to migrate to block storage."
fi

# ── 4. Python venv + pip ────────────────────────────────────
echo "==> Setting up Python venv..."
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip -q
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt" -q

# ── 5. Build Angular frontend ───────────────────────────────
echo "==> Building Angular frontend..."
cd "$APP_DIR/frontend"
npm ci --silent
npx --yes node --max-old-space-size=4096 \
    ./node_modules/@angular/cli/bin/ng build --configuration production --no-progress

mkdir -p "$WWW_DIR"
cp -r "$APP_DIR/frontend/dist/hyderabad-urban-realty/." "$WWW_DIR/"
chown -R www-data:www-data "$WWW_DIR"

# ── 6. Publish .NET backend ─────────────────────────────────
echo "==> Publishing .NET backend..."
cd "$APP_DIR/backend-dotnet"
dotnet publish -c Release -o publish --nologo -q
chown -R www-data:www-data "$APP_DIR/backend-dotnet/publish"

# ── 7. Copy systemd unit files ──────────────────────────────
echo "==> Installing systemd services..."
cp "$APP_DIR/deploy/hur-dotnet.service" /etc/systemd/system/
cp "$APP_DIR/deploy/hur-flask.service"  /etc/systemd/system/
systemctl daemon-reload

# ── 8. Nginx config ─────────────────────────────────────────
echo "==> Configuring nginx..."
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/hyderabad-urban-reality
ln -sf /etc/nginx/sites-available/hyderabad-urban-reality \
         /etc/nginx/sites-enabled/hyderabad-urban-reality
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# ── 9. Log directory for Flask ──────────────────────────────
mkdir -p /var/log/hur-flask
chown www-data:www-data /var/log/hur-flask

# ── 10. .env file check ─────────────────────────────────────
if [ ! -f "$APP_DIR/.env" ]; then
    echo ""
    echo "⚠  No .env file found at $APP_DIR/.env"
    echo "   Copy deploy/.env.example → $APP_DIR/.env and fill in real secrets."
    echo "   Then run: systemctl enable --now hur-dotnet hur-flask"
    echo ""
else
    chown www-data:www-data "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"

    # ── 11. Start / restart services ────────────────────────
    echo "==> Starting services..."
    systemctl enable hur-dotnet hur-flask
    systemctl restart hur-dotnet hur-flask
    systemctl status hur-dotnet --no-pager
    systemctl status hur-flask  --no-pager
fi

echo ""
echo "✅  Deployment complete."
echo "    Frontend : http://$(curl -s ifconfig.me)"
echo "    .NET API : http://localhost:$DOTNET_PORT"
echo "    Flask API: http://localhost:$FLASK_PORT"
