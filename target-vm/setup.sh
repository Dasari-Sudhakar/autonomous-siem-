#!/usr/bin/env bash
# Run THIS script AS ROOT on the target VM (Ubuntu Server 22.04 minimal, 1 GB RAM).
# It installs sshd, Filebeat, the orchestrator SSH pubkey, and passwordless sudo.
#
# Usage (from the target VM, after copying this file to it):
#   sudo ES_HOST=<ubuntu-host-ip> PUBKEY="ssh-ed25519 AAAA..." ./setup.sh

set -euo pipefail

[[ "$EUID" -eq 0 ]] || { echo "Run as root."; exit 1; }
[[ -n "${ES_HOST:-}" ]] || { echo "Set ES_HOST=<ubuntu-host-ip>"; exit 1; }
[[ -n "${PUBKEY:-}" ]] || { echo "Set PUBKEY=<orchestrator ssh pubkey>"; exit 1; }

echo "[+] apt update + base packages"
apt-get update -y
apt-get install -y openssh-server curl wget iptables sudo

echo "[+] Enable sshd"
systemctl enable --now ssh

echo "[+] Allow password auth (so hydra can attempt against this host)"
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
systemctl restart ssh

echo "[+] Create 'siem' user for orchestrator-driven remote actions"
if ! id siem >/dev/null 2>&1; then
    useradd -m -s /bin/bash siem
fi

echo "[+] Grant passwordless sudo for iptables + kill"
cat > /etc/sudoers.d/siem-orchestrator <<EOF
siem ALL=(root) NOPASSWD: /usr/sbin/iptables, /bin/kill, /usr/bin/kill
EOF
chmod 440 /etc/sudoers.d/siem-orchestrator

echo "[+] Install orchestrator SSH pubkey"
install -d -m 700 -o siem -g siem /home/siem/.ssh
echo "$PUBKEY" > /home/siem/.ssh/authorized_keys
chmod 600 /home/siem/.ssh/authorized_keys
chown siem:siem /home/siem/.ssh/authorized_keys

echo "[+] Install Filebeat 8.13.0"
FB=filebeat-8.13.0-amd64.deb
if ! command -v filebeat >/dev/null 2>&1; then
    cd /tmp
    wget -q "https://artifacts.elastic.co/downloads/beats/filebeat/${FB}"
    dpkg -i "${FB}"
fi

echo "[+] Write Filebeat config (auth.log -> ${ES_HOST}:9200)"
cat > /etc/filebeat/filebeat.yml <<EOF
filebeat.modules:
  - module: system
    auth:
      enabled: true
      var.paths: ["/var/log/auth.log*"]
    syslog:
      enabled: false

output.elasticsearch:
  hosts: ["http://${ES_HOST}:9200"]

setup.kibana:
  host: "http://${ES_HOST}:5601"

setup.template.settings:
  index.number_of_shards: 1
  index.number_of_replicas: 0

logging.level: info
EOF

echo "[+] Enable Filebeat + system module"
filebeat modules enable system
systemctl enable --now filebeat

echo ""
echo "============================================================"
echo " Target VM is ready."
echo "============================================================"
echo ""
echo "  Target IP:  $(hostname -I | awk '{print $1}')"
echo "  Filebeat:   shipping /var/log/auth.log -> http://${ES_HOST}:9200"
echo "  SSH user:   siem (key-only, sudo for iptables + kill)"
echo ""
echo "  Verify Filebeat:  systemctl status filebeat"
echo "  Watch auth log:   sudo tail -f /var/log/auth.log"
