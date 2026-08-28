from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from razor.network import Socks5hProxy, SysctlTTL, WarpController, WarpStatus, dns_leak_prevention_environment
from razor.tls_client import PROFILES, TLSClient, TLSProfile, TLSRequestError


ROOT = Path(__file__).resolve().parents[1]


def test_proxy_uses_remote_dns_and_clears_no_proxy() -> None:
    proxy = Socks5hProxy("127.0.0.1", 40000)
    assert proxy.url == "socks5h://127.0.0.1:40000"
    assert proxy.proxies["https"] == proxy.url
    env = dns_leak_prevention_environment(proxy)
    assert env["ALL_PROXY"] == proxy.url
    assert env["NO_PROXY"] == ""


def test_proxy_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        Socks5hProxy("not-an-ip", 40000)
    with pytest.raises(ValueError):
        Socks5hProxy("127.0.0.1", 0)


def test_warp_status_parser() -> None:
    output = "Status update: Connected\nMode: Proxy\nProxy port: 40000\n"

    def runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, output, "")

    status = WarpController(runner=runner).status()
    assert status == WarpStatus(True, "proxy", 40000, output.strip())
    assert status.proxy_enabled


def test_warp_ensure_proxy_runs_configuration_and_connect() -> None:
    calls = []
    connected = [False]

    def runner(command, **kwargs):
        calls.append(command[2:])
        if command[-1] == "status":
            text = "Status update: Connected\nMode: Proxy\nProxy port: 40000" if connected[0] else "Status update: Disconnected"
            return subprocess.CompletedProcess(command, 0, text, "")
        if command[-1] == "connect":
            connected[0] = True
        return subprocess.CompletedProcess(command, 0, "", "")

    status = WarpController(runner=runner).ensure_proxy()
    assert status.connected
    assert ["mode", "proxy"] in calls
    assert ["proxy", "port", "40000"] in calls
    assert ["connect"] in calls


def test_ttl_validation() -> None:
    assert SysctlTTL.validate(64) == 64
    with pytest.raises(ValueError):
        SysctlTTL.validate(0)
    with pytest.raises(ValueError):
        SysctlTTL.validate(256)


def test_ttl_backup_and_restore(monkeypatch, tmp_path: Path) -> None:
    calls = []
    values = iter([128])

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, str(next(values)) if command[-1] == "net.ipv4.ip_default_ttl" else "", "")

    monkeypatch.setattr("razor.network.subprocess.run", fake_run)
    ttl = SysctlTTL(tmp_path / "backup")
    ttl.backup()
    assert "net.ipv4.ip_default_ttl=128" in (tmp_path / "backup").read_text()
    ttl.restore()
    assert not (tmp_path / "backup").exists()
    assert any("net.ipv4.ip_default_ttl=128" in command for command in calls)


def test_tls_headers_preserve_profile_order(monkeypatch) -> None:
    requests = SimpleNamespace(Session=lambda **kwargs: None)
    monkeypatch.setattr("razor.tls_client._load_curl", lambda: requests)
    client = TLSClient(profile=TLSProfile.CHROME, session=SimpleNamespace(request=lambda *a, **k: k))
    assert list(client.headers) == [key for key, _ in PROFILES[TLSProfile.CHROME].headers]


def test_tls_request_injects_proxy_and_headers() -> None:
    captured = {}

    class Session:
        def request(self, method, url, **kwargs):
            captured.update(method=method, url=url, kwargs=kwargs)
            return "response"

    client = TLSClient(session=Session(), proxy="socks5h://127.0.0.1:40000")
    assert client.get("https://example.test", headers={"x-test": "1"}) == "response"
    assert captured["method"] == "GET"
    assert captured["kwargs"]["proxies"]["https"].startswith("socks5h://")
    assert captured["kwargs"]["headers"]["x-test"] == "1"


def test_tls_wraps_transport_error() -> None:
    class Session:
        def request(self, *args, **kwargs):
            raise OSError("network down")

    with pytest.raises(TLSRequestError, match="network down"):
        TLSClient(session=Session()).get("https://example.test")


def test_browser_profile_path_isolated(tmp_path: Path) -> None:
    from razor.browser import CamoufoxBrowser

    browser = CamoufoxBrowser(profile="alice", root=tmp_path)
    assert browser.profile_dir == tmp_path / "alice"
    assert browser.profile_dir != tmp_path / "bob"
    with pytest.raises(ValueError):
        CamoufoxBrowser(profile="../escape", root=tmp_path)


def test_scripts_are_executable_and_present() -> None:
    for name in ("setup.sh", "uninstall.sh", "verify_oracle.py"):
        path = ROOT / "scripts" / name
        assert path.exists()
        assert path.read_text(encoding="utf-8").startswith("#!")


def test_oracle_private_address_detection() -> None:
    namespace = {}
    source = (ROOT / "scripts" / "verify_oracle.py").read_text(encoding="utf-8")
    assert "socks5h" in source
    assert "webrtc_host_candidates" in source
