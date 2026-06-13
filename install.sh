#!/bin/bash

INSTALL_PATH=$PWD
CURRENT_USER=$(whoami)

echo "[*] Installing to: $INSTALL_PATH as user: $CURRENT_USER"


sed -e "s|{{INSTALL_PATH}}|$INSTALL_PATH|g" \
    -e "s|{{USER}}|$CURRENT_USER|g" \
    boatlog.service.template > boatlog.service


if [ ! -f "config.json" ]; then
    echo "[*] Creating default config.json..."
    cat <<EOF > config.json
{
  "signalk_url": "http://localhost:3000",
  "active_dir": "$HOME/.signalk/boatlog_active",
  "speed_start_threshold": 0.5,
  "speed_stop_threshold": 0.2,
  "log_interval": 5,
  "autostop_delay_notification": 600,
  "auto_stop_delay": 300,
  "min_points_to_save": 1
}
EOF
fi


sudo apt update
sudo apt install -y python3-venv
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

sudo cp boatlog.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable boatlog.service
sudo systemctl restart boatlog.service

echo "[+] Installation complete and service started!"