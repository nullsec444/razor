"""Camoufox browser lifecycle and per-profile storage isolation."""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from typing import Any


class BrowserError(RuntimeError):
    """Raised for browser startup or profile lifecycle errors."""


def _camoufox_class():
    try:
        from camoufox.sync_api import Camoufox
    except ImportError as exc:
        raise BrowserError("Camoufox is not installed; install the full dependency set") from exc
    return Camoufox


class CamoufoxBrowser:
    """Synchronous Camoufox wrapper with isolated, persistent Playwright state."""

    def __init__(
        self,
        profile: str = "default",
        root: str | Path | None = None,
        headless: bool = True,
        geoip: bool = True,
        **camoufox_options: Any,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", profile):
            raise ValueError("profile must contain only letters, digits, '.', '_' and '-'")
        self.profile = profile
        self.root = Path(root) if root else Path(tempfile.gettempdir()) / "stealth-core-profiles"
        self.profile_dir = self.root / profile
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.storage_state = self.profile_dir / "storage_state.json"
        self.headless = headless
        self.geoip = geoip
        self.options = dict(camoufox_options)
        self._manager = None
        self.browser = None
        self.context = None

    def start(self) -> "CamoufoxBrowser":
        if self.context is not None:
            return self
        Camoufox = _camoufox_class()
        options = {"headless": self.headless, "geoip": self.geoip, **self.options}
        self._manager = Camoufox(**options)
        try:
            self.browser = self._manager.__enter__()
            context_options: dict[str, Any] = {}
            if self.storage_state.exists():
                context_options["storage_state"] = str(self.storage_state)
            self.context = self.browser.new_context(**context_options)
        except Exception as exc:
            self.close()
            raise BrowserError(f"Camoufox startup failed: {exc}") from exc
        return self

    def new_page(self, **kwargs: Any) -> Any:
        if self.context is None:
            self.start()
        return self.context.new_page(**kwargs)

    def save_storage_state(self) -> Path:
        if self.context is None:
            raise BrowserError("browser is not started")
        self.context.storage_state(path=str(self.storage_state))
        return self.storage_state

    def close(self) -> None:
        context, manager = self.context, self._manager
        self.context = None
        self.browser = None
        self._manager = None
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
        if manager is not None:
            try:
                manager.__exit__(None, None, None)
            except Exception:
                pass

    def delete_profile(self) -> None:
        self.close()
        shutil.rmtree(self.profile_dir, ignore_errors=True)

    def __enter__(self) -> "CamoufoxBrowser":
        return self.start()

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        try:
            if self.context is not None:
                self.save_storage_state()
        finally:
            self.close()
