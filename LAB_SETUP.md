# Day 0 -- Lab Setup

Three boxes:
1. **Ubuntu host** -- runs ELK + the orchestrator. Your dual-boot Ubuntu.
2. **Target VM** -- Ubuntu Server 22.04 minimal, 1 GB RAM, VirtualBox. Runs sshd + Filebeat.
3. **Phone** -- Termux + Hydra. The attacker.

Exit signal for Day 0: hydra from the phone produces failed-SSH entries on the target VM, those entries appear in Kibana within ~10 s.

---

## 1. Ubuntu host prep

```bash
sudo apt update && sudo apt upgrade -y

git clone https://github.com/Dasari-Sudhakar/autonomous-siem-.git
cd autonomous-siem-

./bootstrap.sh    # installs Docker, Python deps, generates SSH key, pulls ELK images
```

**Important:** Bootstrap prints two values you'll need on the target VM:
- The orchestrator SSH **pubkey** (`siem-orchestrator`)
- The Ubuntu host's **LAN IP** (for ES ingest)

Copy both somewhere (paste into a text file, send to yourself via WhatsApp Web, whatever).

If Docker was installed for the first time, log out + log back in before continuing.

Allow ES traffic from the target VM:
```bash
sudo ufw allow from any to any port 9200 proto tcp
```

---

## 2. Wi-Fi / network setup

The phone, the Ubuntu host, and the target VM all need to be on the same network.

**Recommended: phone hotspot mode.** Turn on hotspot on your phone. Connect the Ubuntu laptop to the phone's hotspot. The target VM will use VirtualBox **bridged mode** on the same Wi-Fi interface, getting an IP from the phone's hotspot.

Why hotspot? You control the network. College/home Wi-Fi may block client-to-client traffic, which kills the demo.

Note the IP space the phone hotspot uses -- usually `192.168.43.x` (Android) or `172.20.10.x` (iOS).

---

## 3. Create the target VM in VirtualBox

```bash
sudo apt install -y virtualbox virtualbox-ext-pack
```

Download Ubuntu Server 22.04 ISO (~1.5 GB): https://ubuntu.com/download/server

VirtualBox -> New:
- Name: `siem-target`
- Type: Linux / Ubuntu (64-bit)
- Base memory: **1024 MB** (do not go higher)
- Processors: 1
- Create virtual hard disk, 10 GB, VDI dynamically allocated

Before starting:
- Settings -> Network -> Adapter 1: **Bridged Adapter**, name = your Wi-Fi interface (e.g. `wlp3s0`). Promiscuous mode: Allow All.
- Settings -> Storage -> attach the Ubuntu Server ISO.

Start the VM, install Ubuntu Server. Choices during install:
- Server name: `siem-target`
- Username: `siem` (must match `TARGET_USER` in `.env`)
- Password: anything (you'll SSH in with key after setup)
- **Check "Install OpenSSH server"** during the installer
- Skip snap-store selections
- Reboot when done

Log in. Check the IP:
```bash
ip -4 addr show
```
You should see a `192.168.x.y` on the LAN. **Note this** -- it becomes `TARGET_HOST` in `.env`.

---

## 4. Run target-vm/setup.sh ON THE TARGET

The repo has a setup script. Get it to the target VM:

```bash
# On the target VM:
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/Dasari-Sudhakar/autonomous-siem-.git
cd autonomous-siem-/target-vm

# Replace the values with your real ones (from bootstrap.sh output on the host):
sudo ES_HOST="192.168.x.11" \
     PUBKEY="ssh-ed25519 AAAA... siem-orchestrator" \
     ./setup.sh
```

The script installs sshd config, the orchestrator pubkey, passwordless sudo (`iptables` + `kill` only), Filebeat 8.13, and starts Filebeat shipping to the host's Elasticsearch.

---

## 5. Set up Termux on the phone (attacker)

Install Termux from F-Droid (the Play Store version is outdated; use F-Droid):
https://f-droid.org/en/packages/com.termux/

In Termux:
```bash
pkg update -y
pkg install -y hydra openssh nano

# Test you can reach the target:
ssh wronguser@192.168.x.12     # answer "yes", then password "wrong" -- closes
```

This single failed ssh attempt should already show up in Kibana once ELK is up.

---

## 6. Verification (on the Ubuntu host)

After running `target-vm/setup.sh`:

```bash
# Edit .env to point at your target VM
nano .env
# Set TARGET_HOST=192.168.x.12 (your target VM's bridged IP)

# Start ELK
make up

# Wait ~30s, then verify Filebeat reached ES from the target:
curl -s "http://localhost:9200/filebeat-*/_count" | jq

# Verify orchestrator can SSH into the target:
ssh -i ~/.ssh/siem_orchestrator_ed25519 siem@192.168.x.12 "sudo -n iptables -L | head"
```

If both succeed, **Day 0 is done**.

---

## Day 0 exit checklist

- [ ] Ubuntu host: `bootstrap.sh` ran clean, SSH key generated
- [ ] Target VM: Ubuntu Server installed, bridged network, IP on the LAN
- [ ] Target VM: `target-vm/setup.sh` ran successfully, Filebeat running
- [ ] Phone: Termux + hydra installed, can ssh-attempt the target
- [ ] Host: Filebeat events visible in ES (`curl filebeat-*/_count` > 0)
- [ ] Host: orchestrator SSH key reaches the target with `sudo -n iptables -L`

When all six are ticked, message me and we move to Day 1 (run the orchestrator, fire the first hydra burst, watch the BLOCKED line appear).
