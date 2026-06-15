# Autonomous SIEM — Final Year Project Plan

**Deadline:** 2026-06-14 (4 working days from 2026-06-10)
**Differentiator:** Auto-detect + auto-eradicate + auto-report. No analyst in the loop.

---

## Locked scope (v1 demo)

| Area | Decision |
|---|---|
| Attack vector | SSH brute force (Hydra → sshd) |
| Detection | Sigma-style rule + Isolation Forest (ML second opinion) |
| Response | `iptables` block source IP (TTL 1h, rollback logged) + kill active sessions |
| Stack | Docker Compose: Elasticsearch + Kibana + Filebeat. Python FastAPI orchestrator. SQLite for response audit. |
| Lab | 2 boxes: phone (Termux+Hydra) attacker, single Ubuntu Server VM on Windows running everything (target + SIEM + dashboard). See Architecture below. |
| Report output | Per-incident PDF via Jinja2 + WeasyPrint |

**Cut from v1 (goes in "Future Work"):** port scan detection, SQLi, reverse shell detection, multi-host correlation, SOAR playbook engine, threat intel feeds.

---

## Hardware budget (Windows host: 8 GB RAM, VT-x enabled)

| Component | RAM |
|---|---|
| Windows 11 + Firefox | ~5.0 GB |
| VirtualBox overhead | ~0.3 GB |
| Ubuntu VM allocation (runs ELK + sshd + orchestrator) | 4.0 GB |
| **Buffer** (tight -- close everything else) | ~-1.3 GB |

This is **tight**. The plan only fits if you close every other Windows app during the demo:
- No Chrome, only Firefox with the dashboard tab
- No Spotify, Discord, OneDrive, Teams, Slack, WhatsApp Desktop
- No background browser tabs
- No Windows Update mid-demo

**Inside the 4 GB VM, allocate:**
- Ubuntu Server idle: 0.4 GB
- ES heap (capped 1 GB): 1.5 GB total
- Kibana: 0.7 GB
- Filebeat: 0.1 GB
- FastAPI orchestrator: 0.2 GB
- VM buffer: 1.1 GB

ES heap is set to 1 GB in `docker-compose.yml` (`ES_JAVA_OPTS: -Xms1g -Xmx1g`). Do not change this. If ES OOMs inside the VM, drop heap to 768m or fall back to OpenSearch single-node.

The phone (Termux attacker) costs **zero** host RAM -- runs entirely on the phone.

---

## Architecture

```
[Windows host]                              [Phone / Termux]
  - VirtualBox                                 (hotspot LAN owner)
  - Firefox at http://<vm-ip>:8000/                |
                       ^                          | hydra ssh
                       | dashboard HTML            v
                       |                  +-----------------------+
                       +------------------+ Ubuntu Server VM      |
                                          | (4 GB, bridged)       |
                                          |                       |
                                          |  sshd  (target sshd)  |
                                          |    |                  |
                                          |    v /var/log/auth.log|
                                          |  Filebeat -> ES       |
                                          |    |                  |
                                          |    v                  |
                                          |  Elasticsearch :9200  |
                                          |    |                  |
                                          |    v                  |
                                          |  Orchestrator :8000   |
                                          |   - rule + ML         |
                                          |   - local iptables    |
                                          |   - local kill        |
                                          |   - dashboard HTML    |
                                          |  Kibana :5601         |
                                          +-----------------------+
```

Two physical boxes, three logical roles:

| Where | Role | RAM |
|-------|------|-----|
| Phone (Termux) | Attacker -- runs Hydra | 0 (on phone) |
| Ubuntu Server VM | Target + SIEM + Dashboard (all-in-one) | 4 GB |
| Windows host | Viewer -- Firefox displays dashboard | (host OS) |

The response runs **locally inside the VM** -- the orchestrator runs `sudo iptables` to block the phone's IP, and `sudo kill` to terminate sshd sessions from that IP. Passwordless sudo for iptables and kill only, set up by `bootstrap.sh`.

**Viva framing:**
> "In a production deployment, target endpoints are separate hosts shipping logs to a centralized SIEM cluster, and response actions dispatch remotely via SSH/EDR APIs. For this lab we co-locate the target sshd and the SIEM stack on a single VM to fit the 8 GB total RAM budget. The pipeline (target log -> Filebeat -> Elasticsearch -> rule + IsolationForest -> iptables + session kill -> audit) is identical to a distributed deployment; only the network hop disappears. A second monitored host is a one-line Filebeat config change on that host, listed in Future Work."

---

## Day-by-day

### Day 0 — Tue 2026-06-10 (today, ~6h)
**Goal:** Lab up, logs flowing into Kibana.

1. Boot Ubuntu. Install VirtualBox (or use KVM).
2. Create Kali VM (host-only network with the Ubuntu host). See `LAB_SETUP.md`.
3. On Ubuntu host: install Docker + Docker Compose.
4. Bring up ELK with `docker compose up -d` (compose file ships Day 1).
5. Configure Filebeat to read `/var/log/auth.log` → index `siem-auth-*`.
6. From Kali, try one failed `ssh user@<ubuntu-ip>`. Confirm it appears in Kibana Discover.

**Exit criteria:** failed SSH from Kali shows up in Kibana within 10s.

### Day 1 — Wed 2026-06-11
**Goal:** Detection working end-to-end (alerts written to ES).

1. FastAPI service polls ES every 10s: `sshd Failed password` events grouped by source IP.
2. Rule: `≥5 failures from same IP in 60s → alert`.
3. Collect 1h of benign auth data (you ssh in normally, occasional typos). Use it to fit Isolation Forest on features: `attempts_per_min`, `distinct_users`, `hour_of_day`, `inter_arrival_std`.
4. Score every candidate alert with the rule AND the model. Write to `siem-alerts-*` with `rule_verdict`, `ml_verdict`, `final_verdict` (OR).
5. Verify in Kibana: trigger Hydra, watch alerts appear.

**Exit criteria:** Hydra burst → alert in `siem-alerts-*` within 15s, with both verdicts populated.

### Day 2 — Thu 2026-06-12
**Goal:** Auto-response + eradication + dedup.

1. On `final_verdict=malicious`: shell out to `iptables -A INPUT -s <ip> -j DROP`.
2. Record action in SQLite `responses(id, ip, blocked_at, ttl_sec, rolled_back_at, reason)` AND mirror to `siem-response-*` index.
3. Cleanup job removes iptables rule after TTL, marks `rolled_back_at`.
4. Dedupe: skip IPs already blocked in last 1h.
5. Eradicate: also `pkill` any live sshd session from that IP.

**Exit criteria:** Hydra dies within 30s of starting. Manual rollback works. No duplicate blocks.

### Day 3 — Fri 2026-06-13
**Goal:** Dashboard + PDF report + draft project report.

1. Kibana dashboards (4 panels): live alert feed, blocked IPs table, attacks-over-time histogram, rule-vs-ML agreement pie.
2. Python script: pull a closed incident from ES → render `incident.html.j2` → WeasyPrint to PDF. Includes: timeline, IOCs, ML score, rule trigger, actions taken, rollback steps.
3. Capture real screenshots of dashboards mid-attack for your written project report.
4. Start writing project report (Abstract, Introduction, Architecture, Results).

**Exit criteria:** End-to-end demo runs cleanly. PDF report generated for the attack. 30%+ of written report drafted.

### Day 4 — Sat 2026-06-14
**Goal:** Demo polish, viva prep, buffer.

1. Full dress rehearsal: Hydra → detect → block → Hydra dies → Kibana shows incident → PDF generated. Time it. Aim for <60s wall-clock.
2. Fix any bugs found.
3. Finish written report.
4. Prepare viva talking points (see "Viva defense" below).

**Exit criteria:** You can run the demo three times in a row without intervention.

---

## Risks (be honest — these go in your report's Limitations section)

1. **ML adds little for SSH brute force.** It's a rule-friendly attack. Frame ML honestly: "second-opinion classifier that catches low-and-slow attacks below the rule threshold (e.g., 3 attempts/min over 20min)." Do not claim it beats the rule on raw F1.
2. **ELK on a single laptop is RAM-hungry.** Single-node ES needs ~2GB. If it OOMs, fallback: OpenSearch single-node (lighter) or strip to SQLite + a small FastAPI HTML dashboard. Decide fallback before Day 1 ends.
3. **Auto-response is lab-only.** State this explicitly in the report. Real SOAR uses analyst-in-the-loop or canary blocks. Justify your design as a research prototype for closed environments (honeypots, isolated VLANs).
4. **Single attack vector.** Honest in viva: "demo shows the full pipeline on one well-understood vector; the architecture is designed to accept new detection modules — see Future Work."

---

## Viva defense (rehearse these answers)

- *"Why not just use Wazuh / Splunk / Elastic SIEM?"* → Those require analyst triage. My contribution is the closed-loop auto-response with rollback, not the ingestion layer (which is why I reuse ELK).
- *"How is your ML different from a rule?"* → It's not better on this attack; it's complementary. Demo: lower the rule threshold to 20 attempts and ML still flags slow brute force the rule misses.
- *"What if it blocks a legit user?"* → TTL auto-rollback after 1h, plus the responses table is the audit trail. Show the rollback command live.
- *"Why ELK + Python and not all in Elastic Watcher?"* → Watcher can detect but not eradicate. Python orchestrator owns the response side.

---

## Repo layout (to be created Day 0)

```
E:\Claude MP\10th June\
├── PLAN.md                  (this file)
├── LAB_SETUP.md             (Day 0 setup steps)
├── README.md
├── docker/
│   ├── docker-compose.yml   (ES + Kibana + Filebeat)
│   └── filebeat.yml
├── orchestrator/
│   ├── main.py              (FastAPI app)
│   ├── rules.py
│   ├── ml_model.py
│   ├── responder.py
│   └── requirements.txt
├── ml/
│   ├── train.py
│   └── isolation_forest.pkl
├── reports/
│   ├── incident.html.j2
│   └── generate.py
└── docs/
    ├── architecture.png     (your existing diagram)
    └── results/             (screenshots for project report)
```
