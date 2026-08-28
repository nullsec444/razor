# Исследование 03: Браузерный Рантайм (C++ vs JS Monkeypatch)

## Почему Playwright Stealth не работает
JS-инъекции перехватываются защитами через:
1. `Function.prototype.toString` проверки.
2. Timing-атаки (`performance.now()`).
3. Поиск CDP-артефактов (`cdc_...`).

## Решение: Camoufox
Camoufox патчит движок Gecko на уровне C++:
- Полное отсутствие `navigator.webdriver`.
- Нативный рендеринг шрифтов и Canvas под Linux.
- Защита от утечек WebRTC STUN/TURN.

```python
from camoufox.sync_api import Camoufox

with Camoufox(
    headless=True,
    geoip=True,
    proxy={"server": "socks5://127.0.0.1:40000"}
) as browser:
    page = browser.new_page()
    page.goto("https://browserleaks.com/canvas")
```
