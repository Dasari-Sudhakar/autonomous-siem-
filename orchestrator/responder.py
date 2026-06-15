import logging
import re
import subprocess

from .config import settings

log = logging.getLogger(__name__)


def _iptables(*args) -> bool:
    try:
        subprocess.run(["sudo", "-n", "iptables", *args], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        log.error("iptables %s failed: %s", args, e.stderr.decode(errors="ignore"))
        return False


def block_ip(ip: str) -> bool:
    if settings.dry_run:
        log.info("[DRY-RUN] block %s", ip)
        return True
    return _iptables("-A", "INPUT", "-s", ip, "-j", "DROP")


def unblock_ip(ip: str) -> bool:
    if settings.dry_run:
        return True
    return _iptables("-D", "INPUT", "-s", ip, "-j", "DROP")


def kill_sessions_from(ip: str) -> int:
    """Kill sshd sessions originating from `ip`. Returns count killed."""
    if settings.dry_run:
        return 0
    try:
        out = subprocess.run(
            ["ss", "-tnp", "state", "established"],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        log.error("ss failed: %s", e)
        return 0

    killed = 0
    for line in out.stdout.splitlines():
        if ":22 " not in line or ip not in line:
            continue
        m = re.search(r"pid=(\d+)", line)
        if not m:
            continue
        pid = m.group(1)
        try:
            subprocess.run(["sudo", "-n", "kill", "-9", pid], check=True, capture_output=True)
            killed += 1
        except subprocess.CalledProcessError:
            pass
    return killed
