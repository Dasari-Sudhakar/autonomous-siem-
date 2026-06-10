# Day 0 — Lab Setup (Ubuntu host + Kali VM)

Target: failed SSH from Kali shows up in Kibana within 10s.

---

## 1. Ubuntu host prep (one-time)

```bash
# Update + install essentials
sudo apt update && sudo apt upgrade -y
sudo apt install -y openssh-server git curl ufw python3-venv

# Make sure sshd is running (this is your "target" service)
sudo systemctl enable --now ssh
sudo systemctl status ssh

# Note your host IP on the network the Kali VM will see
ip -4 addr show | grep inet
```

Allow SSH through the firewall for now (we will let our orchestrator manage iptables later):

```bash
sudo ufw allow ssh
sudo ufw --force enable
```

---

## 2. Install Docker + Compose on Ubuntu

```bash
# Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker

# Test
docker run --rm hello-world
docker compose version
```

If Docker pulls fail, you don't have working internet — fix that first.

---

## 3. Create the Kali VM (two options — pick one)

### Option A: VirtualBox (easiest, GUI)

```bash
sudo apt install -y virtualbox virtualbox-ext-pack
```

1. Download Kali VirtualBox image (pre-built `.ova`) from kali.org/get-kali → Virtual Machines.
2. VirtualBox → File → Import Appliance → select the `.ova`.
3. Settings → Network → **Adapter 1: Host-only Adapter** (`vboxnet0`). This puts Kali on a private network with Ubuntu, NO internet, NO risk of escape. Add a second NAT adapter only if Kali needs internet to install tools.
4. **Settings → System → Base Memory: set to exactly 2048 MB** (we're on 8 GB total — don't go higher).
5. Settings → System → Processor: 2 CPUs is fine.
6. Start the VM. Default creds: `kali / kali`.

### Option B: KVM / virt-manager (lighter, no Oracle)

```bash
sudo apt install -y qemu-kvm libvirt-daemon-system virt-manager
sudo usermod -aG libvirt $USER
newgrp libvirt
```

Use virt-manager GUI → New VM → import the Kali ISO → set network to "default" (NAT bridge libvirt creates).

---

## 4. Verify Kali → Ubuntu network path

On Ubuntu host, get its IP on the host-only/libvirt network:
```bash
ip -4 addr show vboxnet0     # or virbr0 for KVM
```

From Kali:
```bash
ping <ubuntu-ip>             # should reply
ssh wronguser@<ubuntu-ip>    # should prompt for password — close it
```

Then on Ubuntu:
```bash
sudo tail -n 5 /var/log/auth.log
# you should see: "Failed password for wronguser from <kali-ip>"
```

If you see that line — the auth log is capturing what we need.

---

## 5. Bring up the ELK stack (Day 0 lite — just verify it boots)

We will write the full `docker-compose.yml` and `filebeat.yml` together once you confirm Steps 1–4 work. For now, sanity-check:

```bash
docker pull docker.elastic.co/elasticsearch/elasticsearch:8.13.0
docker pull docker.elastic.co/kibana/kibana:8.13.0
docker pull docker.elastic.co/beats/filebeat:8.13.0
```

If those three pulls finish, ELK will run on this machine.

**Tuning kernel for ES on 8 GB systems (required, one-time):**
```bash
# ES needs higher vm.max_map_count or it refuses to start
sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

---

## 6. Repo clone (so you have the same files on Ubuntu)

The plan + code live at `E:\Claude MP\10th June` on Windows. Two ways to get it onto Ubuntu:

- **GitHub (recommended):** create a private repo, `git push` from Windows, `git clone` on Ubuntu.
- **NTFS mount:** if the E: drive is NTFS, `sudo mount /dev/sdaX /mnt/work` and work from there directly. Slower, breaks symlinks. Use only if no internet.

---

## Day 0 exit checklist

- [ ] Ubuntu sshd running, reachable from Kali VM
- [ ] Failed SSH attempts from Kali appear in `/var/log/auth.log`
- [ ] Docker + Compose installed
- [ ] ELK images pulled
- [ ] Repo synced to Ubuntu

When all five are ticked, message me and we start Day 1 (write the actual ELK compose file, Filebeat config, and the FastAPI orchestrator skeleton).
