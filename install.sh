#!/bin/bash

# Find den sti hvor install.sh ligger
INSTALL_PATH=$PWD

echo "[*] Installing to: $INSTALL_PATH"

# 1. create the service file from the template, replacing the placeholder with the actual path
sed -e "s|{{INSTALL_PATH}}|$INSTALL_PATH|g" boatlog.service.template > boatlog.service

# make config file if it doesn't exist
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

# install dependencies in a virtual environment
sudo apt update
sudo apt install -y python3-venv
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# install the service
sudo cp boatlog.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable boatlog.service
sudo systemctl start boatlog.service


echo "[+] Installation complete!"