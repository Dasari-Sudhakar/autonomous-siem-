# Target VM setup

This folder contains the script that runs **on the target VM** — the separate
Ubuntu Server 22.04 minimal VM that plays the "victim" sshd role. The phone
(Termux + hydra) attacks this VM. Filebeat on this VM ships `/var/log/auth.log`
to Elasticsearch on the Ubuntu host. The orchestrator on the Ubuntu host SSHes
back into this VM to run `iptables` blocks and kill compromised sessions.

## Prereqs (done on the Ubuntu host before touching the target)

```bash
# Generate the orchestrator's SSH key (bootstrap.sh does this for you):
ssh-keygen -t ed25519 -f ~/.ssh/siem_orchestrator_ed25519 -N "" -C siem-orchestrator
cat ~/.ssh/siem_orchestrator_ed25519.pub   # copy this string
ip -4 addr show                            # note the Ubuntu host IP on the LAN
```

## On the target VM (after Ubuntu Server install)

```bash
# Get this script onto the target. Either clone the repo or scp it from the host:
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/Dasari-Sudhakar/autonomous-siem-.git
cd autonomous-siem-/target-vm

# Run setup with the orchestrator pubkey and Ubuntu host IP:
sudo ES_HOST="192.168.x.11" PUBKEY="ssh-ed25519 AAAA... siem-orchestrator" ./setup.sh
```

Replace `192.168.x.11` with the Ubuntu host's IP on the LAN, and the
`ssh-ed25519 AAAA...` with the pubkey printed by `bootstrap.sh`.

## Verify it works (from the Ubuntu host)

```bash
# 1. Filebeat is shipping
curl -s "http://localhost:9200/filebeat-*/_count" | jq

# 2. Orchestrator can SSH into target (no password prompt, no host-key prompt)
ssh -i ~/.ssh/siem_orchestrator_ed25519 siem@<target-ip> "sudo -n iptables -L | head"
```

## VM specs

- Ubuntu Server 22.04 minimal, no GUI
- 1024 MB RAM, 1 vCPU
- 10 GB disk
- VirtualBox **bridged network** (so the phone on Wi-Fi/hotspot can reach it)

## Why a separate VM and not the host?

Production SIEM deployments separate target hosts from the SIEM cluster.
This lab matches that with one cheap VM as the target. The orchestrator's
response (iptables, kill) lands on the target via SSH, exactly as a real
SOAR action would land on a remote endpoint.
