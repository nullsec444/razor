#!/usr/bin/env python3
"""Fidelity oracle for the network, TLS and browser layers.

The report is intentionally machine-readable.  A missing optional browser or
JA4 oracle is reported as ``unknown`` rather than silently treated as success.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from ipaddress import ip_address, ip_network
from typing import Any

from stealth_core.network import DEFAULT_WARP_PROXY, WarpController
from stealth_core.tls_client import TLSClient, TLSProfile, TLSRequestError


def result(status: str, detail: Any = None) -> dict[str, Any]:
    item = {"status": status}
    if detail is not None:
        item["detail"] = detail
    return item


def check_warp(proxy: str) -> dict[str, Any]:
    report: dict[str, Any] = {}
    try:
        controller = WarpController()
        status = controller.status()
        report["cli"] = result("pass" if status.connected else "fail", {"mode": status.mode, "port": status.proxy_port})
    except Exception as exc:
        report["cli"] = result("unknown", str(exc))
    try:
        with TLSClient(proxy=proxy, timeout=15) as client:
            response = client.get("https://api.ipify.org?format=json")
            response.raise_for_status()
            payload = response.json()
            report["egress"] = result("pass" if payload.get("ip") else "fail", payload)
    except Exception as exc:
        report["egress"] = result("fail", str(exc))
    return report


def check_ja4(proxy: str, profile: TLSProfile) -> dict[str, Any]:
    try:
        with TLSClient(profile=profile, proxy=proxy, timeout=20) as client:
            response = client.get("https://tls.peet.ws/api/all")
            response.raise_for_status()
            payload = response.json()
        tls = payload.get("tls", {})
        ja4 = tls.get("ja4") or payload.get("ja4")
        if not ja4:
            return result("unknown", {"reason": "oracle did not return a JA4 value", "tls": tls})
        return result("pass", {"ja4": ja4, "profile": profile.value})
    except (TLSRequestError, ValueError, KeyError) as exc:
        return result("fail", str(exc))
    except Exception as exc:
        return result("fail", str(exc))


def _is_private(value: str) -> bool:
    try:
        address = ip_address(value)
    except ValueError:
        return False
    private_ranges = (
        ip_network("10.0.0.0/8"),
        ip_network("172.16.0.0/12"),
        ip_network("192.168.0.0/16"),
        ip_network("100.64.0.0/10"),
        ip_network("127.0.0.0/8"),
        ip_network("::1/128"),
        ip_network("fc00::/7"),
        ip_network("fe80::/10"),
    )
    return any(address in network for network in private_ranges)


def check_browser(proxy: str, profile: str) -> dict[str, Any]:
    try:
        from stealth_core.browser import CamoufoxBrowser
        with CamoufoxBrowser(profile=profile, headless=True, geoip=True) as browser:
            page = browser.new_page()
            page.goto("https://cloudflare.com/cdn-cgi/trace", wait_until="domcontentloaded", timeout=30000)
            candidates = page.evaluate("""async () => new Promise(resolve => {
              const found = [];
              const pc = new RTCPeerConnection({iceServers: []});
              pc.onicecandidate = event => {
                if (!event.candidate) { pc.close(); resolve(found); return; }
                const text = event.candidate.candidate || '';
                const match = text.match(/(?:^| )((?:\\d{1,3}\\.){3}\\d{1,3}|[0-9a-f:]+)(?: |$)/i);
                if (match && !found.includes(match[1])) found.push(match[1]);
              };
              pc.createDataChannel('oracle');
              pc.createOffer().then(offer => pc.setLocalDescription(offer));
              setTimeout(() => { pc.close(); resolve(found); }, 8000);
            })""")
            leaked = [candidate for candidate in candidates if _is_private(candidate)]
            return result("pass" if not leaked else "fail", {"host_candidates": candidates, "private_candidates": leaked})
    except Exception as exc:
        return result("unknown", str(exc))


def check_dns_proxy(proxy: str) -> dict[str, Any]:
    try:
        with TLSClient(proxy=proxy, timeout=15) as client:
            response = client.get("https://cloudflare.com/cdn-cgi/trace")
            response.raise_for_status()
            body = response.text
        return result("pass" if "ip=" in body else "fail", {"remote_dns": "socks5h", "bytes": len(body)})
    except Exception as exc:
        return result("fail", str(exc))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proxy", default=DEFAULT_WARP_PROXY)
    parser.add_argument("--profile", choices=[item.value for item in TLSProfile], default=TLSProfile.CHROME.value)
    parser.add_argument("--browser-profile", default="oracle")
    parser.add_argument("--strict", action="store_true", help="return 1 when any check fails")
    args = parser.parse_args()
    profile = TLSProfile(args.profile)
    checks = {
        "l3_warp": check_warp(args.proxy),
        "l7_tls_ja4": check_ja4(args.proxy, profile),
        "dns_remote_resolution": check_dns_proxy(args.proxy),
        "webrtc_host_candidates": check_browser(args.proxy, args.browser_profile),
    }
    failed = any(item.get("status") == "fail" or any(v.get("status") == "fail" for v in item.values() if isinstance(v, dict)) for item in checks.values())
    report = {
        "schema": "stealth-core.oracle/v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "proxy": args.proxy,
        "checks": checks,
        "overall": "fail" if failed else "pass",
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 1 if args.strict and failed else 0


if __name__ == "__main__":
    sys.exit(main())
