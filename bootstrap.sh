#!/usr/bin/env bash
# Autonomous SIEM — one-shot installer for Ubuntu.
# Installs apt deps, Docker, Python venv, tunes kernel for ES, pulls ELK images.
# Re-runnable: skips steps that are already done.

set -euo pipefail

GREEN="\033[32m"; YELLOW="\033[33m"; RED="\033[31m"; RESET="\033[0m"
say()  { echo -e "${GREEN}[+]${RESET} $*"; }
warn() { echo -e "${YELLOW}[!]${RESET} $*"; }
die()  { echo -e "${RED}[x]${RESET} $*"; exit 1; }

[[ "$EUID" -eq 0 ]] && die "Don't run as root. Run as your normal user; sudo is used where needed."
command -v lsb_release >/dev/null || die "Not Debian/Ubuntu. Aborting."

cd "$(dirname "$(readlink -f "$0")")"

say "Updating apt cache..."
sudo apt-get update -y

say "Installing base packages..."
sudo apt-get install -y \
    openssh-server ufw curl wget git make jq \
    python3 python3-venv python3-pip \
    iptables net-tools iproute2 \
    libpango-1.0-0 libpangoft2-1.0-0 \
    build-essential

say "Enabling sshd (this is your TARGET service)..."
sudo systemctl enable --now ssh
sudo ufw allow ssh
sudo ufw --force enable

if ! command -v docker >/dev/null 2>&1; then
    say "Installing Docker..."
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$USER"
    DOCKER_INSTALLED_NOW=1
else
    say "Docker already installed: $(docker --version)"
    DOCKER_INSTALLED_NOW=0
fi

say "Tuning vm.max_map_count for Elasticsearch..."
sudo sysctl -w vm.max_map_count=262144
if ! grep -q "vm.max_map_count" /etc/sysctl.conf; then
    echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf >/dev/null
fi

if [[ "$DOCKER_INSTALLED_NOW" -eq 0 ]] || groups "$USER" | grep -q docker; then
    say "Pulling ELK images (~2 GB total, takes a few minutes)..."
    docker pull docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    docker pull docker.elastic.co/kibana/kibana:8.13.0
    docker pull docker.elastic.co/beats/filebeat:8.13.0
else
    warn "Skipping image pulls — log out + log back in, then re-run: docker pull docker.elastic.co/elasticsearch/elasticsearch:8.13.0"
fi

say "Creating Python venv at .venv ..."
if [[ ! -d .venv ]]; then
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r orchestrator/requirements.txt

say "Creating SQLite data dir..."
sudo mkdir -p /var/lib/siem
sudo chown "$USER":"$USER" /var/lib/siem

say "Creating .env from example..."
[[ -f .env ]] || cp .env.example .env

say "Marking scripts executable..."
chmod +x attack/*.sh kibana/setup.sh 2>/dev/null || true

cat <<EOF

============================================================
 Bootstrap complete.
============================================================

EOF

if [[ "$DOCKER_INSTALLED_NOW" -eq 1 ]]; then
    cat <<EOF
${YELLOW}IMPORTANT:${RESET} Docker was just installed. You MUST log out and
log back in (or run 'newgrp docker') before docker commands
work without sudo. After that, run:

    docker pull docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    docker pull docker.elastic.co/kibana/kibana:8.13.0
    docker pull docker.elastic.co/beats/filebeat:8.13.0

EOF
fi

cat <<EOF
NEXT STEPS:
  1. Set up Kali VM (LAB_SETUP.md sections 3-4)
  2. Start ELK:                make up
  3. Open Kibana:              http://localhost:5601
  4. Generate benign baseline: ./attack/benign_traffic.sh    (let it run ~15 min while you set up Kali)
  5. Train ML model:           make train
  6. Start orchestrator:       make orchestrator
  7. Attack from Kali:         ./attack/ssh_brute.sh <ubuntu-ip>
  8. Watch Kibana + the orchestrator log: BLOCKED message + Kali Hydra dies.
  9. Generate PDF report:      make report ID=1

EOF
