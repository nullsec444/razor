# Браузерный Стек: C++ Injection vs JS-Monkeypatching

## 1. Смерть JS-патчей (Playwright Stealth / Puppeteer Stealth)
Современные антифрод-скрипты (Cloudflare Turnstile, Datadome, Kasada) больше не проверяют тупо `navigator.webdriver`. Они детектят **попытки скрыть автоматизацию**:
- **Proxy/Prototype Trap**: Проверка `Function.prototype.toString.call(navigator.permissions.query)` или `Object.getOwnPropertyDescriptor(navigator, 'webdriver')`. JS-патчи всегда оставляют следы в prototype chain.
- **Timing Attacks**: Вызовы через Proxy работают в десятки раз медленнее нативного C++ кода. Скрипты защиты замеряют дельту времени доступа к свойствам через `performance.now()`.
- **CDP Runtime Flaws**: Подключение через Chrome DevTools Protocol (`--remote-debugging-port`) добавляет скрытые артефакты (`window.cdc_adoQpoasnfa76pfcZLmcfl_...`), которые ищутся антифрод-скриптами за 1 микросекунду.

## 2. Архитектура Camoufox (C++ Native Patches)
Camoufox — это форк Firefox, где модификации внедрены **внутрь движка Gecko на уровне исходного C++ кода**, а не через JS-инъекции.
- Отсутствие `navigator.webdriver` на уровне скомпилированного бинарника.
- Нативная генерация уникальных, но математически консистентных отпечатков WebGL, Canvas, AudioContext и Font List.
- Автоматическая изоляция WebRTC и запрет утечки локальных IP.
- Эмуляция реалистичного рендера шрифтов под Windows/macOS прямо внутри headless Linux без X11.

## 3. Playwright с Camoufox (Zero-Cost Headless Setup)
Запуск полностью невидимого браузера в Python:
```python
from camoufox.sync_api import Camoufox

with Camoufox(
    headless=True,
    geoip=True,  # Автоподгон таймзоны и локали под IP прокси
    proxy={"server": "socks5://127.0.0.1:40000"}  # Интеграция с локальным WARP
) as browser:
    page = browser.new_page()
    page.goto("https://browserleaks.com/canvas")
    # Браузер проходит 100% тестов на фингерпринт без JS-хуков
```

## 4. Консистентность профилей (Zero Entropy Anomaly)
- **Золотое правило**: Внутри одного профиля отпечаток экрана, WebGL и аудио хеш должны быть **строго статичными**.
- Нельзя менять разрешение экрана (`viewport`) и список шрифтов от сессии к сессии — это триггерит флаг подозрительной энтропии.
