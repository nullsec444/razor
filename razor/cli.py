"""
RAZOR Unified Command-Line Interface (CLI).
"""
import sys
import subprocess
import argparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def run_doctor():
    console.print(Panel.fit("[bold cyan]🗡 RAZOR Doctor & Integrity Check[/bold cyan]", border_style="cyan"))
    from razor.network import WarpController, Socks5hProxy
    from razor.tls_client import TLSClient, TLSProfile
    
    table = Table(title="[bold white]Subsystem Integrity Matrix[/bold white]", show_header=True, header_style="bold magenta")
    table.add_column("Subsystem", style="cyan", width=22)
    table.add_column("Target Contract", style="white", width=30)
    table.add_column("Status", justify="center", width=12)
    table.add_column("Observed Detail", style="dim")

    # 1. WARP Daemon & Port Check
    proxy = Socks5hProxy()
    warp = WarpController()
    warp_status = warp.status()
    
    if warp_status.connected and warp_status.mode == "proxy":
        table.add_row("L3/L4 WARP Proxy", "127.0.0.1:40000 (Proxy Mode)", "[bold green]PASS[/bold green]", f"Connected ({warp_status.details})")
    elif warp_status.connected:
        table.add_row("L3/L4 WARP Proxy", "127.0.0.1:40000 (Proxy Mode)", "[bold yellow]WARN[/bold yellow]", f"Connected in mode: {warp_status.mode}")
    else:
        table.add_row("L3/L4 WARP Proxy", "127.0.0.1:40000 (Proxy Mode)", "[bold red]FAIL[/bold red]", "WARP not connected")

    # 2. Remote Egress & Cloudflare Trace
    try:
        with TLSClient(profile=TLSProfile.CHROME, proxy=proxy.url, timeout=10) as client:
            r = client.get("https://cloudflare.com/cdn-cgi/trace")
            lines = dict(line.split("=", 1) for line in r.text.strip().split("\n") if "=" in line)
            egress_ip = lines.get("ip", "Unknown")
            warp_flag = lines.get("warp", "off")
            loc = lines.get("loc", "Unknown")
            
            if warp_flag in ("on", "plus"):
                table.add_row("Anycast Egress", "Cloudflare Consumer Edge", "[bold green]PASS[/bold green]", f"IP: {egress_ip} (loc={loc}, warp={warp_flag})")
            else:
                table.add_row("Anycast Egress", "Cloudflare Consumer Edge", "[bold yellow]WARN[/bold yellow]", f"IP: {egress_ip} (warp=off)")
    except Exception as e:
        table.add_row("Anycast Egress", "Cloudflare Consumer Edge", "[bold red]FAIL[/bold red]", str(e))

    # 3. L7 TLS JA4 Impersonation
    try:
        with TLSClient(profile=TLSProfile.CHROME, proxy=proxy.url, timeout=10) as client:
            r = client.get("https://tls.browserleaks.com/json")
            data = r.json()
            ja4 = data.get("ja4", "N/A")
            table.add_row("L7 BoringSSL JA4", "Chrome 124 ClientHello", "[bold green]PASS[/bold green]", f"JA4: {ja4}")
    except Exception as e:
        table.add_row("L7 BoringSSL JA4", "Chrome 124 ClientHello", "[bold red]FAIL[/bold red]", str(e))

    # 4. Kernel TTL
    try:
        res = subprocess.run(["sysctl", "net.ipv4.ip_default_ttl"], capture_output=True, text=True)
        val = res.stdout.strip().split("=")[-1].strip()
        if val == "128":
            table.add_row("Kernel TCP TTL", "TTL = 128 (Windows/macOS stack)", "[bold green]PASS[/bold green]", f"TTL: {val}")
        else:
            table.add_row("Kernel TCP TTL", "TTL = 128 (Windows/macOS stack)", "[bold yellow]WARN[/bold yellow]", f"TTL: {val} (Linux default 64)")
    except Exception as e:
        table.add_row("Kernel TCP TTL", "TTL = 128", "[bold red]FAIL[/bold red]", str(e))

    console.print(table)
    console.print("\n[bold green]✓ Diagnostic finished.[/bold green]\n")

def main():
    parser = argparse.ArgumentParser(
        prog="razor",
        description="🗡 RAZOR: Zero-Cost Anti-Detect & Protocol-Fidelity CLI"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # doctor
    subparsers.add_parser("doctor", help="Run full diagnostic integrity matrix (WARP, TLS JA4, TTL, Egress)")

    # setup
    setup_parser = subparsers.add_parser("setup", help="Run zero-cost VPS auto-provisioning")
    setup_parser.add_argument("--minimal", action="store_true", help="Minimal setup (Network + L7 only)")
    setup_parser.add_argument("--full", action="store_true", help="Full setup with Camoufox C++ browser")

    # update
    subparsers.add_parser("update", help="Update RAZOR, dependencies, and browser engines")

    # uninstall
    subparsers.add_parser("uninstall", help="Cleanly rollback all host configurations")

    args = parser.parse_args()

    if args.command == "doctor":
        run_doctor()
    elif args.command == "setup":
        flag = "--full" if args.full else ("--minimal" if args.minimal else "--full")
        import os
        script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "setup.sh")
        subprocess.run(["bash", script, flag])
    elif args.command == "update":
        import os
        script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "update.sh")
        subprocess.run(["bash", script])
    elif args.command == "uninstall":
        import os
        script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "uninstall.sh")
        subprocess.run(["bash", script])
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
