# Autonomous SIEM

Final-year project — a SIEM that detects, eradicates, and reports SSH brute-force attacks with **no analyst in the loop**.

- Detection: Sigma-style rule + Isolation Forest as ML second opinion
- Response: `iptables` block + active-session kill (1h TTL, auto-rollback, fully audited)
- Reporting: per-incident PDF via Jinja2 + WeasyPrint
- Stack: Elasticsearch + Kibana + Filebeat + FastAPI + SQLite

## Quick start

Three boxes: **Ubuntu host** (ELK + orchestrator), **target VM** (Ubuntu Server, sshd + Filebeat),
**phone** (Termux + Hydra).

### On the Ubuntu host
```bash
git clone https://github.com/Dasari-Sudhakar/autonomous-siem-.git
cd autonomous-siem-

./bootstrap.sh           # apt + Docker + Python venv + ES tuning + SSH key + image pulls
# (log out/in if Docker was just installed)

# bootstrap prints the orchestrator SSH pubkey + the host's LAN IP -- copy both.

sudo ufw allow from any to any port 9200 proto tcp
make up                  # ES on :9200, Kibana on :5601
```

### On the target VM (Ubuntu Server 22.04, 1 GB RAM, bridged network, OpenSSH-server installed during setup)
```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/Dasari-Sudhakar/autonomous-siem-.git
cd autonomous-siem-/target-vm
sudo ES_HOST="<ubuntu-host-IP>" PUBKEY="<pubkey from bootstrap.sh>" ./setup.sh
```

### Back on the Ubuntu host
```bash
# Set the target VM's IP
sed -i "s|^TARGET_HOST=.*|TARGET_HOST=<target-vm-IP>|" .env

# Verify ingest + remote SSH
curl -s "http://localhost:9200/filebeat-*/_count" | jq
ssh -i ~/.ssh/siem_orchestrator_ed25519 siem@<target-vm-IP> "sudo -n iptables -L | head"

# Generate baseline (15 min of normal ssh attempts) then train ML
ssh -i ~/.ssh/siem_orchestrator_ed25519 siem@<target-vm-IP> "logger -t sshd 'test'"   # quick smoke test
make train

make orchestrator    # leave running
```

### On the phone (Termux from F-Droid)
```bash
pkg install -y hydra
hydra -L users.txt -P pass.txt -t 4 <target-vm-IP> ssh
```

Within ~15 s: orchestrator log prints `BLOCKED <phone-ip>`, the orchestrator SSHes
into the target and runs `iptables` + `kill`, hydra dies. List active blocks:

```bash
curl http://localhost:8000/responses/active
make report ID=1
```

## Repo layout

```
.
├── bootstrap.sh              # one-shot Ubuntu host installer
├── Makefile                  # stage runner
├── PLAN.md                   # day-by-day plan + viva defense
├── LAB_SETUP.md              # 3-box lab walkthrough
├── .env.example              # config (target VM host, SSH key path, etc.)
├── docker/
│   └── docker-compose.yml    # ES + Kibana only (Filebeat lives on target)
├── orchestrator/             # FastAPI app -- runs on Ubuntu host
│   ├── main.py               # /health, /responses/*
│   ├── pipeline.py           # poll loop: ES -> rules -> ML -> remote respond
│   ├── es_client.py
│   ├── rules.py              # threshold rule (5 fails / 60s / IP)
│   ├── ml_model.py           # IsolationForest scorer
│   ├── responder.py          # SSH-into-target: iptables + kill
│   ├── db.py                 # SQLite audit
│   └── config.py             # pydantic-settings (.env-driven)
├── target-vm/                # runs ON the target VM
│   ├── setup.sh              # sshd, Filebeat, sudoers, SSH key install
│   └── README.md
├── ml/
│   └── train.py              # IsolationForest on baseline traffic
├── reports/
│   ├── generate.py           # PDF generator
│   └── incident.html.j2
├── attack/
│   ├── ssh_brute.sh          # hydra wrapper (works from Termux too)
│   ├── benign_traffic.sh     # baseline generator
│   └── termux_setup.md       # phone-side commands
└── kibana/
    └── setup.sh
```

## Hardware

Target system: 8 GB RAM, dual-boot Ubuntu, VT-x enabled. ES heap capped at 1 GB.
See `PLAN.md` for the RAM budget.

## Lab topology

- **Ubuntu host (dual-boot)**: runs Elasticsearch, Kibana, and the FastAPI orchestrator. 8 GB total RAM.
- **Target VM**: Ubuntu Server 22.04 minimal, 1 GB RAM, VirtualBox bridged network. Runs sshd + Filebeat. The orchestrator SSHes into this VM to run remote `iptables` blocks and kill compromised sessions.
- **Phone**: Termux + Hydra. The attacker. Zero host-RAM cost.

This three-box split matches the original architecture diagram literally. See `PLAN.md` for the full architecture and viva framing.

See `LAB_SETUP.md` for the step-by-step lab walkthrough.

## Status & timeline

4-day build, deadline 2026-06-14. `PLAN.md` has the day-by-day. The code scaffolding is in place — Days 1–3 are about getting it running on real lab traffic, tuning the ML threshold, building Kibana dashboards, and writing the project report.
