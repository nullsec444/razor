"""
L7 Protocol Fidelity & TLS Impersonation via curl_cffi.
Supports both synchronous TLSClient and asynchronous AsyncTLSClient.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, Tuple, List, Sequence


class TLSProfile(str, Enum):
    CHROME = "chrome"
    SAFARI = "safari"


@dataclass(frozen=True)
class ProfileDefinition:
    name: str
    impersonate: str
    headers: Tuple[Tuple[str, str], ...]


CHROME_HEADERS: Tuple[Tuple[str, str], ...] = (
    ("sec-ch-ua", '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"'),
    ("sec-ch-ua-mobile", "?0"),
    ("sec-ch-ua-platform", '"macOS"'),
    ("upgrade-insecure-requests", "1"),
    ("user-agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    ("accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"),
    ("sec-fetch-site", "none"),
    ("sec-fetch-mode", "navigate"),
    ("sec-fetch-user", "?1"),
    ("sec-fetch-dest", "document"),
    ("accept-language", "en-US,en;q=0.9"),
)

SAFARI_HEADERS: Tuple[Tuple[str, str], ...] = (
    ("user-agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"),
    ("accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
    ("accept-language", "en-US,en;q=0.9"),
    ("sec-fetch-dest", "document"),
    ("sec-fetch-mode", "navigate"),
    ("sec-fetch-site", "none"),
)

PROFILES: Dict[TLSProfile, ProfileDefinition] = {
    TLSProfile.CHROME: ProfileDefinition("chrome", "chrome124", CHROME_HEADERS),
    TLSProfile.SAFARI: ProfileDefinition("safari", "safari17_0", SAFARI_HEADERS),
}


class TLSRequestError(RuntimeError):
    """Raised for network or TLS negotiation failures."""


def _load_curl():
    try:
        from curl_cffi import requests
        return requests
    except ImportError as exc:
        raise TLSRequestError("curl_cffi is not installed") from exc


class TLSClient:
    def __init__(
        self,
        profile: TLSProfile = TLSProfile.CHROME,
        proxy: Optional[str] = "socks5h://127.0.0.1:40000",
        timeout: int = 15,
        session: Any = None,
        headers: Optional[Dict[str, str]] = None
    ) -> None:
        self.profile = profile if isinstance(profile, TLSProfile) else TLSProfile(profile)
        self.definition = PROFILES[self.profile]
        self.proxy = proxy
        self.timeout = timeout
        self.headers = dict(self.definition.headers)
        if headers:
            self.headers.update(headers)

        if session is not None:
            self.session = session
        else:
            requests = _load_curl()
            proxies = {"all": self.proxy, "http": self.proxy, "https": self.proxy} if self.proxy else None
            self.session = requests.Session(
                impersonate=self.definition.impersonate,
                proxies=proxies,
                timeout=self.timeout,
                headers=self.headers,
            )

    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        proxies = {"all": self.proxy, "http": self.proxy, "https": self.proxy} if self.proxy else None
        merged_headers = self.headers.copy()
        if "headers" in kwargs and kwargs["headers"]:
            merged_headers.update(kwargs["headers"])
        
        req_kwargs = {
            "proxies": proxies,
            "timeout": self.timeout,
            **kwargs,
            "headers": merged_headers,
        }
        
        try:
            return self.session.request(method, url, **req_kwargs)
        except Exception as exc:
            raise TLSRequestError(f"TLS request failed: {exc}") from exc

    def get(self, url: str, **kwargs: Any) -> Any:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Any:
        return self.request("POST", url, **kwargs)

    def export_cookies_json(self) -> str:
        cookies_list = []
        if hasattr(self.session, "cookies") and hasattr(self.session.cookies, "jar"):
            for cookie in self.session.cookies.jar:
                cookies_list.append({
                    "name": cookie.name,
                    "value": cookie.value,
                    "domain": cookie.domain,
                    "path": cookie.path,
                    "secure": cookie.secure,
                    "expires": cookie.expires
                })
        return json.dumps(cookies_list, indent=2)

    def close(self) -> None:
        if hasattr(self.session, "close"):
            try:
                self.session.close()
            except Exception:
                pass

    def __enter__(self) -> "TLSClient":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


class AsyncTLSClient:
    def __init__(
        self,
        profile: TLSProfile = TLSProfile.CHROME,
        proxy: Optional[str] = "socks5h://127.0.0.1:40000",
        timeout: int = 15,
        headers: Optional[Dict[str, str]] = None
    ) -> None:
        self.profile = profile if isinstance(profile, TLSProfile) else TLSProfile(profile)
        self.definition = PROFILES[self.profile]
        self.proxy = proxy
        self.timeout = timeout
        self.headers = dict(self.definition.headers)
        if headers:
            self.headers.update(headers)

        requests = _load_curl()
        proxies = {"all": self.proxy, "http": self.proxy, "https": self.proxy} if self.proxy else None
        self.session = requests.AsyncSession(
            impersonate=self.definition.impersonate,
            proxies=proxies,
            timeout=self.timeout,
            headers=self.headers,
        )

    async def request(self, method: str, url: str, **kwargs: Any) -> Any:
        try:
            return await self.session.request(method, url, **kwargs)
        except Exception as exc:
            raise TLSRequestError(f"Async TLS request failed: {exc}") from exc

    async def get(self, url: str, **kwargs: Any) -> Any:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> Any:
        return await self.request("POST", url, **kwargs)

    async def close(self) -> None:
        if hasattr(self.session, "close"):
            await self.session.close()

    async def __aenter__(self) -> "AsyncTLSClient":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()
