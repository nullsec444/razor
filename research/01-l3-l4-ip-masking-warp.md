# Исследование 01: L3/L4 Маскировка датацентровых IP

## Проблема
Датацентровые ASN (Hetzner, OVH, AWS, DigitalOcean) в базах IP-репутации имеют `Fraud Score = 100`. Прямые запросы сразу получают капчу или HTTP 403.

## Решение через Cloudflare WARP Anycast
WARP туннелирует трафик в Anycast-сеть Cloudflare. Входящий на целевой сайт трафик имеет IP Cloudflare Consumer Edge, что полностью убирает маркер хостинга.

### Настройка SOCKS5 Прокси:
```bash
warp-cli --accept-tos register
warp-cli --accept-tos set-mode proxy
warp-cli --accept-tos set-proxy-port 40000
warp-cli --accept-tos connect
```
Трафик перенаправляется через протокол `socks5h://127.0.0.1:40000` (буква `h` гарантирует удаленный DNS резолв).
