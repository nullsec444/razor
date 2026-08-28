# Context: Zero-Cost Anti-Detect & Web Automation Architecture

## Background
The commercial anti-detect market relies heavily on upselling expensive residential proxy pools ($5–10/GB) and paid browser licenses.

In over 95% of real-world scenarios, automated requests are blocked not due to raw IP reputation alone, but because of protocol and client-stack desynchronization (L7 TLS ClientHello, HTTP/2 framing mismatches, host DNS leakage via `socks5://` instead of `socks5h://`, and JavaScript proxy detection traps like `navigator.webdriver = false`).

## Engineering Goals
Provide a completely free, autonomous, and production-ready stealth environment for AI agents:
1. **L3/L4 Network Layer**: Zero-cost Cloudflare Anycast WARP tunneling via local SOCKS5 proxy on port 40000.
2. **L7 TLS/JA4 Matching**: `curl_cffi` BoringSSL integration matching Chrome 124+ and Safari profiles.
3. **Browser Runtime**: Native C++ Camoufox (Gecko) engine eliminating JavaScript monkey-patching leaks.
4. **Automated Setup**: Turnkey node provisioning in `Fast Install` on any standard Linux VPS.
