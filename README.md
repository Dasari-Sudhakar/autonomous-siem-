# Autonomous SIEM

Final-year project -- a SIEM that detects, eradicates, and reports SSH brute-force attacks with **no analyst in the loop**.

- Detection: Sigma-style rule + Isolation Forest as ML second opinion
- Response: local `iptables` block + active-session kill (1h TTL, auto-rollback, fully audited)
- Reporting: per-incident PDF via Jinja2 + WeasyPrint
- Live dashboard: single-page status console served by the orchestrator at port 8000
- Stack: Elasticsearch + Kibana + Filebeat + FastAPI + SQLite

## Topology

- **Windows host (your laptop)**: runs VirtualBox + Firefox. Used to view the dashboard.
- **Ubuntu Server VM (inside VirtualBox, 4 GB RAM, bridged network)**: runs **everything else** -- sshd target, ELK stack, FastAPI orchestrator, dashboard server.
- **Phone (Termux + Hydra)**: attacker. Attacks the VM's IP over the LAN.

Single all-in-one VM by design to fit 8 GB total RAM with Windows running. Viva framing: production deployments separate target and SIEM; this lab co-locates them to fit the hardware.

## Quick start

### Inside the Ubuntu VM (after Ubuntu Server install)

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/Dasari-Sudhakar/autonomous-siem-.git
cd autonomous-siem-

./bootstrap.sh           # apt + Docker + Python venv + ES tuning + sudoers + image pulls
# (log out / back in if Docker was just installed, then re-run bootstrap)

make up                  # ES :9200, Kibana :5601, Filebeat shipping /var/log/auth.log

# generate a baseline so the ML model has data
./attack/benign_traffic.sh 127.0.0.1 15

make train               # train Isolation Forest on the baseline
make orchestrator        # FastAPI + dashboard on :8000 (leave running)
```

### On Windows
Open Firefox at `http://<vm-ip>:8000/` -- live dashboard.

### On the phone (Termux from F-Droid)
```bash
pkg install -y hydra
hydra -L users.txt -P pass.txt -t 4 <vm-ip> ssh
```

Within ~15s: dashboard banner turns red, `BLOCKED <phone-ip>` row appears, hydra dies. Click the PDF link in the row to download the incident report.

```bash
# Active blocks (JSON)
curl http://<vm-ip>:8000/responses/active

# Regenerate a PDF report
make report ID=1
```

## Repo layout

```
.
├── bootstrap.sh              # one-shot installer (runs INSIDE the VM)
├── Makefile                  # stage runner
├── PLAN.md                   # day-by-day plan + viva defense
├── LAB_SETUP.md              # Windows + VirtualBox + Ubuntu VM walkthrough
├── .env.example
├── docker/
│   ├── docker-compose.yml    # ES + Kibana + Filebeat (1GB ES heap)
│   └── filebeat.yml
├── orchestrator/             # FastAPI app
│   ├── main.py               # /, /health, /responses, /api/events, /api/alerts, /api/incident
│   ├── dashboard.html        # single-page live dashboard (served at /)
│   ├── pipeline.py           # poll ES -> rules + ML -> respond
│   ├── es_client.py
│   ├── rules.py              # 5 fails / 60s / IP
│   ├── ml_model.py           # IsolationForest scorer
│   ├── responder.py          # local iptables block + session kill
│   ├── db.py                 # SQLite responses audit
│   └── config.py
├── ml/
│   └── train.py
├── reports/
│   ├── generate.py           # PDF generator
│   └── incident.html.j2
├── attack/
│   ├── ssh_brute.sh          # hydra wrapper (works from Termux too)
│   ├── benign_traffic.sh
│   └── termux_setup.md
└── kibana/
    └── setup.sh
```

## Hardware

- Windows host with 8 GB total RAM, VT-x enabled
- VirtualBox VM gets 4 GB; close other apps on Windows during demo
- See `PLAN.md` for the RAM budget breakdown
