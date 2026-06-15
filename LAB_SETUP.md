# Lab Setup -- Windows host + Ubuntu VM

Two machines:
1. **Ubuntu Server VM** on Windows (VirtualBox, 4 GB RAM, bridged network). Runs everything: sshd, ELK, orchestrator, dashboard.
2. **Phone** with Termux + Hydra. The attacker.

Windows itself just runs Firefox to view the dashboard at the VM's IP.

Exit signal for Day 0: failed SSH from the phone appears in the dashboard at `http://<vm-ip>:8000/` within ~15s.

---

## 1. Install VirtualBox on Windows

Download from https://www.virtualbox.org/wiki/Downloads -> Windows hosts -> install with defaults.

Also install the **Extension Pack** from the same page (lets bridged networking work cleanly).

---

## 2. Get the Ubuntu Server ISO

Download Ubuntu Server 22.04 LTS from https://ubuntu.com/download/server (~1.5 GB).

Pick the **server** ISO, not desktop. Lower RAM, no GUI overhead.

---

## 3. Network: turn on phone hotspot before creating the VM

Why hotspot: you own the network, no college Wi-Fi blocking client-to-client. Phone, Windows, and the VM all sit on the same hotspot subnet.

Turn on hotspot on the phone. Connect the Windows laptop to it.

---

## 4. Create the VM in VirtualBox

VirtualBox -> New:
- Name: `siem-allinone`
- Type: Linux / Ubuntu (64-bit)
- Base memory: **4096 MB**
- Processors: 2
- Hard disk: VDI, 20 GB, dynamically allocated

Before you start it -- settings:
- **Network -> Adapter 1: Bridged Adapter**, Name = the Wi-Fi adapter you're connected to (the phone hotspot). Promiscuous mode: Allow All.
- Storage -> attach the Ubuntu Server ISO to the optical drive.

---

## 5. Install Ubuntu Server inside the VM

Boot the VM. Walk through the installer:
- Server name: `siem`
- Username: anything you like (e.g. `siem`) -- this is the user the orchestrator will run as
- Password: anything memorable
- **Check "Install OpenSSH server"** during the installer (important)
- Skip snap-store selections
- Reboot when done. The ISO will eject itself.

Log in. Check the IP:
```bash
ip -4 addr show
```

Note the bridged IP (likely `192.168.x.y` or `172.20.10.x` on iOS hotspot). **You will use this from Windows and from the phone.**

---

## 6. Run the project bootstrap inside the VM

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/Dasari-Sudhakar/autonomous-siem-.git
cd autonomous-siem-
./bootstrap.sh
```

Bootstrap installs Docker, Python deps, pulls ELK images, tunes the kernel for ES, sets up passwordless sudo for `iptables` and `kill`, and prints your VM's IP.

If Docker was just installed: `logout` and log back in (so the docker group takes effect), then run `./bootstrap.sh` once more to finish the image pulls.

---

## 7. Set up Termux on the phone

Install Termux from **F-Droid** (NOT Play Store -- Play Store version is frozen):
https://f-droid.org/en/packages/com.termux/

In Termux:
```bash
pkg update -y
pkg install -y hydra openssh

# Smoke test: one failed ssh attempt against the VM
ssh wronguser@<vm-ip>     # press y, type any wrong password
```

You should see the failed entry in the VM:
```bash
sudo tail -n 3 /var/log/auth.log
# Failed password for wronguser from <phone-ip>
```

---

## 8. Start the SIEM stack (inside the VM)

```bash
make up                   # ES + Kibana + Filebeat in Docker
# wait ~30s for Kibana to be reachable
curl -s http://localhost:9200/filebeat-*/_count | jq
# count should grow each time you fail-ssh from the phone

make orchestrator         # FastAPI + dashboard on port 8000
```

Now open Firefox **on Windows** at:

```
http://<vm-ip>:8000/
```

You should see the live dashboard.

---

## 9. The first attack

In Termux on the phone:

```bash
# Wordlists (one-time)
printf 'root\nadmin\nubuntu\nguest\nsiem\ntest\n' > users.txt
printf 'password\n123456\nadmin\nletmein\nubuntu\nqwerty\npass\n' > pass.txt

# Attack
hydra -L users.txt -P pass.txt -t 4 <vm-ip> ssh
```

In ~15s the dashboard banner flips to red, an active block appears, the "Sessions killed" counter shows >0, and hydra dies on the phone. Click the PDF link in the dashboard to download the incident report.

---

## Day 0 exit checklist

- [ ] VirtualBox installed on Windows
- [ ] Ubuntu Server VM created (4 GB RAM, bridged), Ubuntu installed
- [ ] `bootstrap.sh` ran clean inside the VM
- [ ] `make up` brings up ES + Kibana + Filebeat, no errors in `docker compose ps`
- [ ] Dashboard reachable from Windows at `http://<vm-ip>:8000/`
- [ ] Phone Termux + hydra installed
- [ ] One manual `ssh wronguser@<vm-ip>` from phone appears in Kibana / `filebeat-*` index

When all seven are ticked, you're ready for Day 1 (`make train` + first hydra burst against the running orchestrator).
