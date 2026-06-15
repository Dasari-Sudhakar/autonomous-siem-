# Autonomous SIEM

Final-year project — a SIEM that detects, eradicates, and reports SSH brute-force attacks with **no analyst in the loop**.

- Detection: Sigma-style rule + Isolation Forest as ML second opinion
- Response: `iptables` block + active-session kill (1h TTL, auto-rollback, fully audited)
- Reporting: per-incident PDF via Jinja2 + WeasyPrint
- Stack: Elasticsearch + Kibana + Filebeat + FastAPI + SQLite

## Quick start (Ubuntu host)

```bash
git clone https://github.com/Dasari-Sudhakar/autonomous-siem-.git
cd autonomous-siem-

# 1. One-shot install (apt deps, Docker, Python venv, ES kernel tuning, image pulls)
./bootstrap.sh

# If Docker was installed for the first time: log out, log back in, then continue.

# 2. Allow the orchestrator to run iptables and kill without a password prompt
echo "$USER ALL=(root) NOPASSWD: /usr/sbin/iptables, /bin/kill" | sudo tee /etc/sudoers.d/siem-orchestrator
sudo chmod 440 /etc/sudoers.d/siem-orchestrator

# 3. Bring up ELK
make up                          # ES on :9200, Kibana on :5601

# 4. Generate ~15 min of benign baseline so ML has something to learn
./attack/benign_traffic.sh 127.0.0.1 15

# 5. Train the Isolation Forest
make train

# 6. Start the orchestrator (leave running in one terminal)
make orchestrator

# 7. From Kali (in another terminal):
./attack/ssh_brute.sh <ubuntu-host-ip>

# 8. Watch the orchestrator log -- you'll see BLOCKED <kali-ip> within ~15s.
#    Hydra dies. Kibana shows the alert + response. List active blocks:
curl http://localhost:8000/responses/active

# 9. Generate a PDF report for an incident
make report ID=1
```

## Repo layout

```
.
├── bootstrap.sh              # one-shot installer
├── Makefile                  # stage runner
├── PLAN.md                   # day-by-day plan + viva defense
├── LAB_SETUP.md              # Ubuntu + Kali VM lab steps
├── .env.example
├── docker/
│   ├── docker-compose.yml    # ES + Kibana + Filebeat (1GB ES heap)
│   └── filebeat.yml
├── orchestrator/             # FastAPI app
│   ├── main.py               # FastAPI entry, /health, /responses/*
│   ├── pipeline.py           # poll loop: ES → rules → ML → respond
│   ├── es_client.py
│   ├── rules.py              # threshold rule (5 fails / 60s / IP)
│   ├── ml_model.py           # Isolation Forest scorer
│   ├── responder.py          # iptables block + session kill
│   ├── db.py                 # SQLite responses audit
│   └── config.py             # pydantic settings (.env-driven)
├── ml/
│   └── train.py              # train IsolationForest on benign baseline
├── reports/
│   ├── generate.py           # PDF generator
│   └── incident.html.j2      # report template
├── attack/
│   ├── ssh_brute.sh          # hydra wrapper (run from Kali)
│   └── benign_traffic.sh     # generate baseline for ML training
└── kibana/
    └── setup.sh              # import dashboards (exported on Day 3)
```

## Hardware

Target system: 8 GB RAM, dual-boot Ubuntu, VT-x enabled. ES heap capped at 1 GB.
See `PLAN.md` for the RAM budget.

## Lab topology

- **Ubuntu host (dual-boot)**: runs ELK + orchestrator + the target `sshd`. Co-located by design to fit 8 GB RAM.
- **Kali (VM in Ubuntu, VirtualBox host-only network, 2 GB RAM)**: attacker, runs Hydra.

The original architecture diagram has Target and SIEM as separate boxes — we collapse them onto one host because the data flow (auth.log → Filebeat → ES → orchestrator → iptables) is identical. See `PLAN.md` for the viva framing of this choice. A real second target is a one-line Filebeat config change, listed in Future Work.

See `LAB_SETUP.md` for the lab walkthrough.

## Status & timeline

4-day build, deadline 2026-06-14. `PLAN.md` has the day-by-day. The code scaffolding is in place — Days 1–3 are about getting it running on real lab traffic, tuning the ML threshold, building Kibana dashboards, and writing the project report.
