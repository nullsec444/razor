"""Network isolation primitives.

The module deliberately uses ``socks5h`` rather than ``socks5``.  The ``h``
variant makes hostname resolution happen at the proxy and prevents the local
resolver from seeing application DNS requests.
"""

from __future__ import annotations

import ipaddress
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

DEFAULT_WARP_HOST = "127.0.0.1"
DEFAULT_WARP_PORT = 40000
DEFAULT_WARP_PROXY = f"socks5h://{DEFAULT_WARP_HOST}:{DEFAULT_WARP_PORT}"


class NetworkError(RuntimeError):
    """Raised when a network isolation operation cannot be completed."""


@dataclass(frozen=True)
class WarpStatus:
    connected: bool
    mode: str | None = None
    proxy_port: int | None = None
    raw: str = ""

    @property
    def proxy_enabled(self) -> bool:
        return self.mode is not None and self.mode.lower() == "proxy"


class Socks5hProxy:
    """Validated proxy configuration suitable for curl-cffi and subprocesses."""

    def __init__(self, host: str = DEFAULT_WARP_HOST, port: int = DEFAULT_WARP_PORT) -> None:
        try:
            ipaddress.ip_address(host)
        except ValueError as exc:
            raise ValueError(f"proxy host must be an IP address: {host!r}") from exc
        if not 1 <= int(port) <= 65535:
            raise ValueError("proxy port must be between 1 and 65535")
        self.host = host
        self.port = int(port)

    @property
    def url(self) -> str:
        return f"socks5h://{self.host}:{self.port}"

    @property
    def proxies(self) -> dict[str, str]:
        return {"http": self.url, "https": self.url}

    def environment(self, base: Mapping[str, str] | None = None) -> dict[str, str]:
        env = dict(base or os.environ)
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            env[key] = self.url
        env["NO_PROXY"] = ""
        env["no_proxy"] = ""
        return env


class WarpController:
    """Small, testable wrapper around the Cloudflare WARP CLI."""

    def __init__(
        self,
        proxy: Socks5hProxy | None = None,
        executable: str = "warp-cli",
        runner=subprocess.run,
    ) -> None:
        self.proxy = proxy or Socks5hProxy()
        self.executable = executable
        self._runner = runner

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        command = [self.executable, "--accept-tos", *args]
        try:
            result = self._runner(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise NetworkError(f"unable to execute {self.executable}: {exc}") from exc
        if check and result.returncode != 0:
            detail = (result.stderr or result.stdout or "command failed").strip()
            raise NetworkError(f"{' '.join(command)}: {detail}")
        return result

    def status(self) -> WarpStatus:
        result = self._run("status", check=False)
        raw = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0:
            return WarpStatus(False, raw=raw.strip())
        connected = bool(re.search(r"(?:Status update|Status)\s*:\s*Connected", raw, re.I))
        mode_match = re.search(r"Mode\s*:\s*([A-Za-z-]+)", raw, re.I)
        port_match = re.search(r"(?:Proxy port|Port)\s*:\s*(\d+)", raw, re.I)
        return WarpStatus(
            connected=connected,
            mode=mode_match.group(1).lower() if mode_match else None,
            proxy_port=int(port_match.group(1)) if port_match else None,
            raw=raw.strip(),
        )

    def configure_proxy(self) -> WarpStatus:
        self._run("mode", "proxy")
        self._run("proxy", "port", str(self.proxy.port))
        return self.status()

    def connect(self) -> WarpStatus:
        status = self.status()
        if not status.connected:
            self._run("connect")
        return self.status()

    def disconnect(self) -> WarpStatus:
        self._run("disconnect", check=False)
        return self.status()

    def ensure_proxy(self) -> WarpStatus:
        status = self.configure_proxy()
        if not status.connected:
            status = self.connect()
        if not status.connected:
            raise NetworkError(f"WARP did not become connected: {status.raw}")
        if status.mode and status.mode.lower() != "proxy":
            raise NetworkError(f"WARP is not in proxy mode: {status.raw}")
        if status.proxy_port and status.proxy_port != self.proxy.port:
            raise NetworkError(f"unexpected WARP proxy port: {status.proxy_port}")
        return status


def dns_leak_prevention_environment(proxy: Socks5hProxy | None = None) -> dict[str, str]:
    """Return an environment where all common proxy variables use remote DNS."""

    return (proxy or Socks5hProxy()).environment()


class SysctlTTL:
    """Manage the default IPv4 TTL with an explicit backup and restoration path."""

    key = "net.ipv4.ip_default_ttl"

    def __init__(self, backup_path: str | Path = "/var/lib/stealth-core/sysctl.backup") -> None:
        self.backup_path = Path(backup_path)

    @staticmethod
    def validate(value: int) -> int:
        value = int(value)
        if not 1 <= value <= 255:
            raise ValueError("IPv4 TTL must be between 1 and 255")
        return value

    def read(self) -> int:
        result = subprocess.run(["sysctl", "-n", self.key], check=True, capture_output=True, text=True)
        return self.validate(result.stdout.strip())

    def backup(self) -> Path:
        self.backup_path.parent.mkdir(parents=True, exist_ok=True)
        self.backup_path.write_text(f"{self.key}={self.read()}\n", encoding="utf-8")
        return self.backup_path

    def set(self, value: int, backup: bool = True) -> int:
        value = self.validate(value)
        if backup and not self.backup_path.exists():
            self.backup()
        subprocess.run(["sysctl", "-w", f"{self.key}={value}"], check=True, capture_output=True, text=True)
        return value

    def restore(self) -> int | None:
        if not self.backup_path.exists():
            return None
        line = self.backup_path.read_text(encoding="utf-8").strip()
        value = self.validate(int(line.split("=", 1)[1]))
        subprocess.run(["sysctl", "-w", f"{self.key}={value}"], check=True, capture_output=True, text=True)
        self.backup_path.unlink()
        return value


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None
