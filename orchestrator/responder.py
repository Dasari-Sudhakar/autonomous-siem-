"""Remote responder.

The orchestrator runs on the Ubuntu host. The target sshd lives on a separate
VM. So iptables and session-kill have to land on the target, not on the host
running this code. We reach the target over SSH using a pre-shared key set up
by bootstrap.sh + target-vm/setup.sh.
"""
import logging
import os
import re
import subprocess

from .config import settings

log = logging.getLogger(__name__)


def _remote(cmd: list[str]) -> tuple[bool, str]:
    """Run a command on the target VM via SSH. Returns (ok, stdout-or-stderr)."""
    if settings.dry_run:
        log.info("[DRY-RUN] remote: %s", " ".join(cmd))
        return True, ""

    key_path = os.path.expanduser(settings.target_ssh_key)
    ssh_cmd = [
        "ssh",
        "-i", key_path,
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", f"ConnectTimeout={settings.target_ssh_timeout}",
        f"{settings.target_user}@{settings.target_host}",
        *cmd,
    ]
    try:
        out = subprocess.run(
            ssh_cmd, check=True, capture_output=True, text=True,
            timeout=settings.target_ssh_timeout + 5,
        )
        return True, out.stdout
    except subprocess.CalledProcessError as e:
        log.error("remote cmd failed (%s): %s", e.returncode, e.stderr.strip())
        return False, e.stderr
    except subprocess.TimeoutExpired:
        log.error("remote cmd timed out: %s", cmd)
        return False, "timeout"


def block_ip(ip: str) -> bool:
    ok, _ = _remote(["sudo", "-n", "iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"])
    return ok


def unblock_ip(ip: str) -> bool:
    ok, _ = _remote(["sudo", "-n", "iptables", "-D", "INPUT", "-s", ip, "-j", "DROP"])
    return ok


def kill_sessions_from(ip: str) -> int:
    """Kill any active sshd sessions on the target originating from `ip`."""
    ok, out = _remote(["ss", "-tnp", "state", "established"])
    if not ok:
        return 0

    killed = 0
    for line in out.splitlines():
        if ":22 " not in line or ip not in line:
            continue
        m = re.search(r"pid=(\d+)", line)
        if not m:
            continue
        pid = m.group(1)
        ok2, _ = _remote(["sudo", "-n", "kill", "-9", pid])
        if ok2:
            killed += 1
    return killed
