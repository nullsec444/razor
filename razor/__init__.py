"""
RAZOR: Routed, Aligned, Zero-leak, Origin-consistent Requests.
"""
from razor.network import Socks5hProxy, WarpController
from razor.tls_client import TLSClient, AsyncTLSClient, TLSProfile
from razor.browser import CamoufoxBrowser, BrowserError

__version__ = "0.1.0"
__all__ = [
    "Socks5hProxy",
    "WarpController",
    "TLSClient",
    "AsyncTLSClient",
    "TLSProfile",
    "CamoufoxBrowser",
    "BrowserError",
]
