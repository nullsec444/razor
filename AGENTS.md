# AGENTS.md — Stealth Core Engine

## Архитектурные Принципы
1. **Zero-Cost Invariant**: Запрещены любые платные внешние зависимости (платные прокси, платные антидетект-сервисы, платные капча-солверы). Решение базируется на открытом C-стеке, Cloudflare WARP SOCKS5 и C++ браузерных ядрах.
2. **Deterministic Speed (Fast Install setup)**: Скрипт `scripts/setup.sh` должен отрабатывать на чистой Ubuntu 22.04/24.04 менее чем за 60 секунд.
3. **Fail-Safe Network**: WARP настраивается исключительно в режиме `set-mode proxy` на порт `40000`. Запрещено переписывать дефолтный сетевой интерфейс (`set-mode warp`), чтобы не ронять SSH-соединение хоста.
4. **Executable Standard of Completion**: Любое изменение в коде или скилле валидируется прогоном `pytest tests/test_e2e.py`, проверяющим:
   - Доступность SOCKS5h WARP прокси на 127.0.0.1:40000.
   - Чистый статус Cloudflare Anycast IP.
   - Идентичность JA4 TLS-отпечатка Chrome.
   - Отсутствие утечек WebRTC и DNS.
