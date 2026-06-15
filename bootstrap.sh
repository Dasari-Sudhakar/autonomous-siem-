#!/usr/bin/env bash
# Autonomous SIEM -- one-shot installer.
# Run this INSIDE the Ubuntu Server VM (all-in-one: target sshd + ELK + orchestrator).
# Re-runnable: skips steps already done.

set -euo pipefail

GREEN="\033[32m"; YELLOW="\033[33m"; RED="\033[31m"; RESET="\033[0m"
say()  { echo -e "${GREEN}[+]${RESET} $*"; }
warn() { echo -e "${YELLOW}[!]${RESET} $*"; }
die()  { echo -e "${RED}[x]${RESET} $*"; exit 1; }

[[ "$EUID" -eq 0 ]] && die "Don't run as root. Use your normal user; sudo is invoked where needed."
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

say "Enabling sshd (this is the TARGET service the phone will attack)..."
sudo systemctl enable --now ssh
sudo ufw allow ssh
sudo ufw allow 8000/tcp   # dashboard
sudo ufw allow 5601/tcp   # Kibana
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
    say "Pulling ELK images (~2 GB total)..."
    docker pull docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    docker pull docker.elastic.co/kibana/kibana:8.13.0
    docker pull docker.elastic.co/beats/filebeat:8.13.0
else
    warn "Skipping image pulls -- log out + log back in, then re-run."
fi

say "Granting passwordless sudo for iptables + kill (orchestrator response actions)..."
SUDOERS=/etc/sudoers.d/siem-orchestrator
if [[ ! -f $SUDOERS ]]; then
    echo "$USER ALL=(root) NOPASSWD: /usr/sbin/iptables, /bin/kill, /usr/bin/kill" | sudo tee $SUDOERS >/dev/null
    sudo chmod 440 $SUDOERS
fi

say "Setting up Python virtualenv..."
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

VM_IP=$(ip -4 addr show | awk '/inet / && $2 !~ /^127/ {gsub(/\/.*/, "", $2); print $2}' | head -1)

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
VM IP on the LAN: ${VM_IP:-unknown}
  -> attack from phone:        hydra -L u -P p ${VM_IP:-<vm-ip>} ssh
  -> view dashboard from Win:  http://${VM_IP:-<vm-ip>}:8000/
  -> view Kibana from Win:     http://${VM_IP:-<vm-ip>}:5601/

NEXT STEPS:

  1. Start ELK:                make up
  2. Verify ingest (after ~30s):
       curl -s http://localhost:9200/filebeat-*/_count | jq
  3. Generate baseline:        ./attack/benign_traffic.sh 127.0.0.1 15
  4. Train ML model:           make train
  5. Start orchestrator:       make orchestrator
       Open http://${VM_IP:-<vm-ip>}:8000/ in Windows Firefox.
  6. Set up Termux on phone:   pkg install hydra openssh
  7. Attack from phone:        hydra -L u -P p ${VM_IP:-<vm-ip>} ssh
  8. Watch dashboard: BLOCKED appears, hydra dies.
  9. Generate PDF report:      make report ID=1   (or click PDF in the dashboard)

EOF
