#!/usr/bin/env bash
# One-time setup of the EC2 instance. Run it once over SSH, as the normal login user (ubuntu / ec2-user):
#
#   scp deploy/setup-ec2.sh deploy/lawbuddy.env.example <user>@<host>:~
#   ssh <user>@<host> 'bash setup-ec2.sh'
#
# Installs Docker and the compose plugin (Ubuntu or Amazon Linux 2023), adds 2 GB of swap (a t3.micro has 1 GB of
# RAM) and creates /opt/lawbuddy. Then edit /opt/lawbuddy/lawbuddy.env with your keys.
set -euo pipefail

DIR=/opt/lawbuddy
ME="$(id -un)"

echo "== Docker"
if ! command -v docker > /dev/null; then
  if command -v apt-get > /dev/null; then
    sudo apt-get update -y
    sudo apt-get install -y docker.io docker-compose-v2 curl
  elif command -v dnf > /dev/null; then
    sudo dnf install -y docker
    sudo mkdir -p /usr/local/lib/docker/cli-plugins
    arch="$(uname -m)"
    sudo curl -fsSL "https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-${arch}" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose
    sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
  else
    echo "unsupported OS: install Docker and the compose plugin yourself" >&2; exit 1
  fi
fi
sudo systemctl enable --now docker
sudo usermod -aG docker "$ME"

echo "== Swap (2 GB)"
if ! sudo swapon --show | grep -q /swapfile; then
  sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab > /dev/null
fi

echo "== $DIR"
sudo mkdir -p "$DIR/logs"
sudo chown -R "$ME:$ME" "$DIR"
sudo chown 1000:1000 "$DIR/logs"          # the container runs as uid 1000 and writes its turn log here
[ -f "$DIR/.env" ] || printf 'API_IMAGE=\n' > "$DIR/.env"
if [ ! -f "$DIR/lawbuddy.env" ]; then
  cp "$HOME/lawbuddy.env.example" "$DIR/lawbuddy.env" 2>/dev/null || touch "$DIR/lawbuddy.env"
  chmod 600 "$DIR/lawbuddy.env"
fi

echo
echo "Done. Next:"
echo "  1. Put your keys in $DIR/lawbuddy.env   (nano $DIR/lawbuddy.env)"
echo "  2. Security group inbound: 22 (your IP) and 8000."
echo "  3. Log out and in again (docker group), then push to main: GitHub Actions deploys."
