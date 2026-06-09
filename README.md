# Autonomous SIEM

Final year project — a SIEM that detects, eradicates, and reports on threats without an analyst in the loop.

**Status:** scoping / Day 0 of 4. See [PLAN.md](PLAN.md) and [LAB_SETUP.md](LAB_SETUP.md).

## Scope (v1)
- Detects SSH brute force via Sigma-style rule + Isolation Forest ML model
- Auto-blocks source IP (`iptables`, TTL 1h, rollback logged)
- Auto-generates per-incident PDF report
- Built on ELK (Elasticsearch + Kibana + Filebeat) + Python FastAPI orchestrator

## Lab topology
- **Host:** Ubuntu (dual-boot) — runs ELK + orchestrator + target sshd
- **VM in host:** Kali Linux — attacker, runs Hydra

## Deadline
2026-06-14
