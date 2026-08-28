# Исследование 02: Согласование L7 TLS, JA4 и HTTP/2

## Механика Детекта TLS
WAF анализирует пакет `Client Hello`:
- Набор и порядок Cipher Suites.
- Порядок TLS Extensions и эллиптических кривых.
- Подпись JA3/JA4.

Стандартный OpenSSL в Python выдает сигнатуру скрипта автоматизации.

## Решение: curl_cffi
Использование нативного бинарного форка cURL, собранного с BoringSSL:
```python
from curl_cffi import requests
response = requests.get(
    "https://tls.browserleaks.com/json",
    impersonate="chrome124",
    proxies={"all": "socks5h://127.0.0.1:40000"}
)
```
