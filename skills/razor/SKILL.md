---
name: RAZOR
description: Routed, Aligned, Zero-leak, Origin-consistent Requests. Fail-closed automation through WARP SOCKS5h with curl_cffi and Camoufox.
---

# RAZOR

**Routed, Aligned, Zero-leak, Origin-consistent Requests**

RAZOR — транспортный контур для разрешённой веб-автоматизации и тестирования собственных систем:

- единая точка выхода через WARP SOCKS5;
- proxy-side DNS resolution;
- L7/TLS-профили через `curl_cffi`;
- отдельный браузерный lane через Camoufox;
- отключение или ограничение WebRTC;
- TTL/Hop Limit = 128 на узле;
- отсутствие direct fallback;
- диагностика дрейфа до выполнения задачи.

RAZOR не используется для обхода аутентификации, CAPTCHA, WAF, ограничений доступа, массового создания аккаунтов или работы с чужими системами без разрешения.

---

## 1. Инварианты

| ID | Требование |
|---|---|
| RZR-01 | SOCKS listener доступен только на `127.0.0.1:40000` |
| RZR-02 | HTTP-клиент использует `socks5h://`, DNS не уходит напрямую |
| RZR-03 | При недоступности прокси выполнение прекращается |
| RZR-04 | API lane и Browser lane не делят cookies, токены и session identity |
| RZR-05 | TLS-профиль не меняется внутри одной API-сессии |
| RZR-06 | User-Agent и ClientHello не рандомизируются на каждом запросе |
| RZR-07 | WebRTC отключён, если он не нужен приложению |
| RZR-08 | Перед задачей выполняется preflight через контролируемый diagnostic URL |
| RZR-09 | Разрешены только hosts из `RAZOR_ALLOWED_HOSTS` |
| RZR-10 | Прямой сетевой fallback запрещён |

Главное правило:

> Стабильный и проверяемый профиль лучше случайного набора признаков.

---

## 2. Архитектура
