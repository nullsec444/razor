# Contributing to RAZOR

We welcome contributions to the RAZOR protocol and stealth engine!

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/nullsec444/stealth-core.git
   cd stealth-core
   ```
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[full]"
   ```
3. Run tests before submitting a PR:
   ```bash
   pytest -v tests/
   ```

## Design Principles
- **Zero-Cost**: Never introduce required paid SaaS/proxy dependencies.
- **Fail-Closed**: If proxy/TLS cannot be guaranteed, fail explicitly.
- **No JS-Monkeypatching**: Use native C++ browser extensions (Camoufox).
