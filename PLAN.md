# Инженерный план реализации `stealth-core`

> Ограничение: в текущем интерфейсе у меня нет прямого доступа к `~/projects/stealth-core/`, поэтому я не могу фактически прочитать `context.md`, `prompt.md` и `AGENTS.md`. План ниже построен на предоставленных требованиях. Первым обязательным шагом должна быть сверка плана с реальным содержимым этих файлов и фиксация расхождений через ADR, а не молчаливое изменение исходных инвариантов.

---

## 0. Цель, границы и инженерные инварианты

### 0.1. Цель системы

`stealth-core` должен предоставлять воспроизводимый тестовый контур для:

- легитимного Synthetic User Monitoring;
- E2E-проверок веб-сервисов через туннель;
- диагностики ложных срабатываний WAF;
- проверки согласованности сетевого, TLS, HTTP/2 и браузерного профиля;
- обнаружения DNS, WebRTC и storage leaks;
- получения машиночитаемого отчёта о fidelity, а не субъективного результата «похоже на браузер».

Система не должна обещать «невидимость» или обход контроля. Она должна измерять и обеспечивать протокольную согласованность в рамках разрешённых тестовых стендов.

### 0.2. Жёсткие инварианты

1. **Zero-Cost**
   - Никаких платных прокси, SaaS-оракулов и подписочных API.
   - Все обязательные проверки должны работать на локальном или self-hosted стеке.
   - Внешние бесплатные диагностические сайты допустимы только как необязательный smoke-тест, но не как CI oracle.

2. **Non-destructive setup**
   - `scripts/setup.sh` не меняет SSH-конфигурацию.
   - Не заменяет default route.
   - Не включает глобальный killswitch.
   - Не применяет глобальные firewall/sysctl-настройки без явного флага.
   - Не перезапускает сеть и не делает reboot.
   - Все изменения инвентаризируются и могут быть удалены через `scripts/uninstall.sh`.

3. **Setup SLA**
   - Целевой bootstrap: менее 60 секунд на поддерживаемом чистом Ubuntu/Debian VPS.
   - SLA измеряется на заранее определённых образах и при определённой минимальной скорости сети.
   - Без фиксированных образов, bandwidth и доступности upstream-репозиториев абсолютная гарантия `<60 секунд` технически невозможна.
   - Поэтому нужны два режима:
     - `bootstrap-minimal`: сеть + Python runtime + smoke test, цель `<60 сек`;
     - `bootstrap-full`: включая крупный браузерный bundle, с отдельным SLA либо использованием заранее собранного release artifact/cache.

4. **Протокольная честность**
   - Никаких тестов, которые всегда возвращают pass.
   - Непроверяемые свойства получают статус `unsupported` или `inconclusive`, а не `passed`.
   - JA4, HTTP/2-профиль и TTL проверяются на стороне контролируемого collector-а.
   - Browser fingerprint не подменяется JavaScript-инъекциями, если это нарушает DOM/runtime integrity.

5. **Безопасная область применения**
   - E2E по умолчанию разрешается только для allowlist доменов.
   - Нагрузочные режимы отсутствуют.
   - Никаких credential stuffing, CAPTCHA bypass или обхода авторизации.
   - Логи не должны содержать cookie, bearer token, пароли или полный browser storage.

---

# 1. Целевая архитектура

## 1.1. Потоки данных

### L7 HTTP harness

```text
pytest / CLI
    |
    v
curl_cffi + pinned impersonation profile
    |
    | SOCKS5h 127.0.0.1:40000
    v
Cloudflare WARP local proxy
    |
    v
WARP egress
    |
    v
Owned fidelity collector / target allowlist
```

### Browser E2E

```text
pytest / CLI
    |
    v
Camoufox launcher + ephemeral native Firefox profile
    |
    | SOCKS5 with proxy-side DNS
    v
Cloudflare WARP local proxy
    |
    v
Owned browser probe / target allowlist
```

### Oracle

```text
Server-side collector observations:
- egress IP and ASN
- DNS correlation
- TCP/IP metadata, where observable
- TLS ClientHello / JA4
- ALPN
- HTTP/2 settings and frame characteristics
- HTTP headers

Browser-side probe:
- WebRTC candidates
- timezone / locale
- navigator and screen values
- storage state
- DOM integrity canaries
- DNS/proxy reachability

                    |
                    v
Normalized observation JSON
                    |
                    v
Policy evaluator
                    |
                    v
PASS / FAIL / INCONCLUSIVE + evidence
```

---

## 1.2. Предлагаемая структура репозитория

```text
stealth-core/
├── AGENTS.md
├── context.md
├── prompt.md
├── README.md
├── SECURITY.md
├── LICENSE
├── CHANGELOG.md
├── pyproject.toml
├── uv.lock
├── Makefile
├── .env.example
├── .gitignore
├── .editorconfig
├── .pre-commit-config.yaml
│
├── scripts/
│   ├── setup.sh
│   ├── uninstall.sh
│   ├── doctor.sh
│   ├── smoke.sh
│   ├── package-release.sh
│   └── lib/
│       ├── common.sh
│       ├── os.sh
│       ├── warp.sh
│       └── systemd.sh
│
├── systemd/
│   ├── stealth-warp.service
│   ├── stealth-warp-health.service
│   └── stealth-warp-health.timer
│
├── config/
│   ├── default.toml
│   ├── fidelity-policy.toml
│   ├── profiles/
│   │   ├── chrome-linux.toml
│   │   └── firefox-linux.toml
│   └── schemas/
│       ├── observation.schema.json
│       ├── report.schema.json
│       └── manifest.schema.json
│
├── src/stealth_core/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── errors.py
│   ├── logging.py
│   ├── models.py
│   │
│   ├── network/
│   │   ├── warp.py
│   │   ├── socks.py
│   │   ├── dns.py
│   │   ├── ttl.py
│   │   └── health.py
│   │
│   ├── l7/
│   │   ├── client.py
│   │   ├── profiles.py
│   │   ├── headers.py
│   │   ├── tls.py
│   │   └── http2.py
│   │
│   ├── browser/
│   │   ├── launcher.py
│   │   ├── profile.py
│   │   ├── proxy.py
│   │   ├── geo.py
│   │   ├── webrtc.py
│   │   └── storage.py
│   │
│   ├── oracle/
│   │   ├── client.py
│   │   ├── normalize.py
│   │   ├── rules.py
│   │   ├── scoring.py
│   │   └── report.py
│   │
│   └── diagnostics/
│       ├── doctor.py
│       └── bundle.py
│
├── collector/
│   ├── README.md
│   ├── compose.yaml
│   ├── Dockerfile
│   ├── src/
│   ├── schemas/
│   └── tests/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   ├── fixtures/
│   ├── test_network_fidelity.py
│   ├── test_l7_fidelity.py
│   ├── test_browser_fidelity.py
│   └── test_e2e_fidelity.py
│
├── research/
│   ├── 01-network-warp-socks-ttl.md
│   ├── 02-tls-ja4-http2.md
│   ├── 03-camoufox-gecko-integrity.md
│   └── 04-e2e-oracle-threat-model.md
│
├── docs/
│   ├── architecture.md
│   ├── quickstart.md
│   ├── configuration.md
│   ├── troubleshooting.md
│   ├── fidelity-model.md
│   ├── release-process.md
│   └── adr/
│       ├── 0001-zero-cost.md
│       ├── 0002-no-global-routing-mutation.md
│       ├── 0003-owned-fidelity-collector.md
│       └── 0004-version-pinned-profiles.md
│
└── skill/
    ├── SKILL.md
    ├── references/
    └── scripts/
```

---

# 2. Engineering flow: фазы и tracer-bullet тикеты

Каждый tracer bullet должен проходить вертикально через минимально необходимый стек и завершаться исполняемой проверкой. Нельзя сначала месяц строить все абстракции, а затем впервые запускать сеть.

---

## Фаза 0. Discovery, аудит и фиксация контрактов

### TB-000: Проверка исходного контекста

**Задачи:**

1. Прочитать `context.md`, `prompt.md`, `AGENTS.md`.
2. Извлечь:
   - обязательные команды;
   - запрещённые действия;
   - ожидаемый формат `SKILL.md`;
   - поддерживаемые ОС;
   - ожидаемые версии WARP, Python, `curl_cffi`, Camoufox;
   - существующие partial implementations.
3. Составить `docs/context-audit.md`:
   - requirement;
   - source file/section;
   - implementation owner;
   - acceptance test;
   - статус.

**DoD:**

- Нет требования без acceptance test или явно указанного статуса `research-required`.
- Все противоречия оформлены как ADR.
- Репозиторий запускает существующие тесты без изменения поведения.

### TB-001: Baseline и capability matrix

Создать матрицу:

| Capability | Ubuntu 22.04 | Ubuntu 24.04 | Debian 12 |
|---|---:|---:|---:|
| WARP package available | | | |
| proxy mode | | | |
| configurable port 40000 | | | |
| curl_cffi wheel | | | |
| Camoufox artifact | | | |
| systemd | | | |

**DoD:**

- Для каждой ОС есть реальный smoke log.
- Неподдерживаемая комбинация явно блокируется setup-скриптом.
- Нет «best effort» продолжения после критической ошибки.

### TB-002: JSON-контракты до реализации

Определить:

- `EnvironmentManifest`;
- `NetworkObservation`;
- `TlsObservation`;
- `Http2Observation`;
- `BrowserObservation`;
- `FidelityReport`.

Обязательные поля каждого наблюдения:

```json
{
  "schema_version": "1.0",
  "run_id": "uuid",
  "timestamp": "RFC3339",
  "status": "pass|fail|inconclusive|unsupported",
  "evidence": {},
  "errors": []
}
```

**DoD:**

- JSON Schema проверяется в CI.
- Добавлены golden fixtures.
- Неизвестные или отсутствующие обязательные поля приводят к contract failure.

---

## Фаза 1. Первый вертикальный срез: WARP → SOCKS5h → collector

### TB-101: Идемпотентный setup WARP

Реализовать минимальный `scripts/setup.sh`, который:

1. Проверяет root/sudo.
2. Определяет ОС через `/etc/os-release`.
3. Устанавливает только необходимые пакеты.
4. Устанавливает WARP из проверенного официального источника.
5. Запускает daemon.
6. Регистрирует клиент, если регистрация отсутствует.
7. Включает proxy mode.
8. Настраивает порт `40000`.
9. Проверяет SOCKS handshake.
10. Не меняет default route.

**DoD:**

- Первый запуск успешен.
- Второй запуск не вносит изменений и завершается успешно.
- SSH-сессия не обрывается.
- `ip route show default` до и после совпадает.
- `ss -lntp` подтверждает listener только на `127.0.0.1:40000` или отдельно согласованных loopback-адресах.
- Smoke request через SOCKS5h возвращает collector observation.

### TB-102: Network doctor

Команда:

```bash
stealth-core doctor --section network --json
```

Проверяет:

- daemon active;
- CLI/daemon version;
- proxy mode;
- port;
- loopback binding;
- SOCKS5 CONNECT;
- SOCKS5 remote DNS;
- egress differs from direct route;
- отсутствие случайного global route takeover.

**DoD:**

- Каждая проверка имеет remediation hint.
- Exit codes стабильны:
  - `0` — всё обязательное исправно;
  - `1` — fidelity failure;
  - `2` — configuration error;
  - `3` — unsupported environment;
  - `4` — transient dependency error.

### TB-103: Простейший E2E

```bash
stealth-core probe http \
  --url https://collector.example/probe \
  --proxy socks5h://127.0.0.1:40000
```

**DoD:**

- Collector видит корреляционный `run_id`.
- DNS-резолвинг target hostname не выполняется локальным клиентом.
- Отчёт сохраняется как JSON.
- Direct и WARP egress различимы.

---

## Фаза 2. Надёжный сетевой модуль

### TB-201: Абстракция WARP lifecycle

`network/warp.py` должен предоставлять:

```python
class WarpController:
    def status(self) -> WarpStatus: ...
    def ensure_registered(self) -> None: ...
    def ensure_proxy_mode(self, port: int) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def healthcheck(self) -> HealthResult: ...
```

Не привязывать основную логику к одному текстовому формату CLI. Сделать version-aware adapter:

- обнаружение версии;
- capability detection;
- таблица поддерживаемых команд;
- нормализация статуса;
- явный `UnsupportedWarpVersion`.

**DoD:**

- Unit-тесты на canned CLI output нескольких версий.
- Ошибки CLI не проглатываются.
- Команды логируются без секретов и registration data.

### TB-202: systemd units

Предпочтительно не подменять vendor unit `warp-svc`. Добавить собственные units только для:

- post-start reconciliation proxy mode;
- healthcheck;
- периодической диагностики.

Требования:

- `After=network-online.target warp-svc.service`;
- `Wants=network-online.target`;
- `Restart=on-failure`;
- hardening:
  - `NoNewPrivileges=true`;
  - `PrivateTmp=true`;
  - `ProtectSystem=strict` там, где совместимо;
  - минимальный `ReadWritePaths`;
- таймауты запуска;
- отсутствие restart loop.

**DoD:**

- `systemd-analyze verify` проходит.
- После reboot порт восстанавливается.
- При отсутствии сети service не зависает бесконечно.
- Health timer не создаёт заметную нагрузку.

### TB-203: SOCKS5h и DNS leak prevention

Проверить отдельно:

1. SOCKS5 TCP CONNECT.
2. Резолвинг случайного уникального hostname через proxy.
3. Отсутствие этого hostname в локальном DNS collector/log.
4. Browser DNS routed through proxy.
5. Негативный тест: `socks5://` вместо `socks5h://` должен обнаруживаться конфиг-валидатором.

**DoD:**

- L7-клиент принимает только `socks5h://` по умолчанию.
- Browser prefs включают proxy DNS.
- Тест с уникальным hostname доказывает отсутствие локального lookup.
- DNS test не полагается только на `/etc/resolv.conf`.

### TB-204: TTL matching — исследование и честная реализация

Критически важно: при работе через локальный WARP SOCKS proxy исходящий TCP flow к target создаётся WARP-компонентом, а не `curl_cffi`. Приложение не может гарантированно установить внешний TTL через `IP_TTL` на своём локальном SOCKS-соединении.

Поэтому:

- не применять глобально `net.ipv4.ip_default_ttl=128`;
- не считать локальный TTL доказательством внешнего TTL;
- измерять TTL на owned collector, насколько это позволяет точка наблюдения;
- сохранять raw observed TTL и метод измерения;
- учитывать decrement по пути;
- профиль задавать как диапазон/классификацию, а не всегда как точное `128`.

Возможные результаты capability probe:

- `observable-and-matching`;
- `observable-but-mismatching`;
- `not-controllable-via-warp-proxy`;
- `not-observable`.

**DoD:**

- `research/01` содержит экспериментальные pcap/collector evidence.
- CI не выдаёт ложный pass для TTL.
- Никакие глобальные sysctl/mangle rules не применяются по умолчанию.
- Если строгое требование «remote peer must infer initial TTL=128» невозможно с выбранным транспортом, pipeline честно падает как `unsupported`, а не маскирует ограничение.

---

## Фаза 3. L7-модуль: `curl_cffi`, TLS/JA4 и HTTP/2

### TB-301: Pinned impersonation profiles

Создать модель:

```python
@dataclass(frozen=True)
class L7Profile:
    name: str
    curl_cffi_version: str
    impersonate_target: str
    expected_alpn: tuple[str, ...]
    expected_ja4: tuple[str, ...]
    expected_http_versions: tuple[str, ...]
    header_policy: str
```

Правила:

- версии `curl_cffi` и профиля зафиксированы;
- upgrade выполняется отдельным PR;
- upgrade PR обязан обновить golden observations;
- нельзя использовать `latest` как production profile.

**DoD:**

- Один стабильный Chrome-like профиль проходит end-to-end.
- Несовпадение installed version с manifest блокирует strict mode.
- В отчёте указаны точные версии библиотеки, libcurl backend и profile ID.

### TB-302: TLS/JA4 verification

Collector должен фиксировать:

- TLS version;
- cipher suites;
- extension IDs и порядок;
- supported groups;
- signature algorithms;
- ALPN;
- GREASE presence;
- SNI presence;
- JA4/JA4-like canonical representation;
- raw ClientHello digest либо bounded diagnostic representation.

Проверка должна учитывать:

- допустимые GREASE-вариации;
- version-specific allowlist JA4;
- различия retry/HelloRetryRequest;
- TLS termination: collector должен наблюдать соединение напрямую, без CDN/reverse proxy, меняющего ClientHello.

**DoD:**

- JA4 вычисляется серверной стороной.
- Есть positive и deliberately mismatched negative test.
- Collector topology документирована.
- Нельзя получить pass, просто передав ожидаемый JA4 в request header.

### TB-303: HTTP/2 verification

Collector должен фиксировать:

- negotiated ALPN;
- SETTINGS IDs, values и порядок;
- initial stream/window behavior;
- PRIORITY behavior, если применимо;
- pseudo-header ordering;
- regular header ordering;
- HEADERS/CONTINUATION shape в пределах возможностей collector-а;
- protocol fallback;
- invalid connection reuse.

Важно:

- в HTTP/2 имена headers обязаны быть lowercase;
- требование «header casing» применимо к HTTP/1.1, но для HTTP/2 критерием является корректная lowercase-нормализация;
- нельзя смешивать Chrome TLS-профиль с произвольным, противоречащим ему H2 framing.

**DoD:**

- Отдельно тестируются HTTP/1.1 и HTTP/2.
- HTTP/2 casing всегда lowercase.
- Порядок pseudo-headers проверяется отдельно от обычных headers.
- H2 profile имеет versioned golden fixture.
- Fallback в HTTP/1.1 при strict-H2 режиме является failure.

### TB-304: Header policy

Запрещено бездумно хардкодить полный набор browser headers.

Header policy должна разделять:

1. автоматически создаваемые impersonation backend;
2. application headers;
3. запрещённые caller overrides;
4. correlation headers для owned collector;
5. HTTP/1.1 casing policy;
6. HTTP/2 lowercase policy.

Нужно проверять согласованность:

- `User-Agent` с профилем;
- `Accept`;
- `Accept-Language` с locale;
- `Accept-Encoding` с реальной поддержкой decompression;
- client hints с выбранным browser profile;
- `Origin`/`Referer` с navigation context;
- отсутствие противоречивых заголовков.

**DoD:**

- Нельзя задать два конфликтующих `User-Agent`.
- Нельзя объявить unsupported content encoding.
- Порядок проверяется сервером, а не по локальной структуре Python.
- Секретные headers редактируются в логах.

---

## Фаза 4. Browser E2E: Camoufox/Gecko

### TB-401: Version-pinned browser artifact

Зафиксировать:

- Camoufox release;
- Firefox/Gecko base version;
- Playwright/Python bindings;
- checksum browser artifact;
- supported CPU architectures;
- системные библиотеки.

Не компилировать Gecko на чистом VPS во время `<60 сек` setup. Использовать:

- проверенный prebuilt artifact;
- release bundle;
- локальный cache;
- checksum verification.

**DoD:**

- Artifact воспроизводимо скачивается.
- SHA-256 проверяется до запуска.
- Несовместимая архитектура завершается `unsupported`.
- Версия browser runtime попадает в report.

### TB-402: Native launcher и DOM integrity

`browser/launcher.py` должен:

- создавать процесс браузера без shell interpolation;
- использовать временный профиль;
- передавать proxy preferences до первого network request;
- не подменять fingerprint через page-level JS;
- не устанавливать расширения без явной необходимости;
- закрывать process tree после теста;
- собирать crash logs.

Под «C++ DOM integrity» должен пониматься приоритет нативного поведения Gecko/патчей browser layer над JavaScript monkey-patching.

DOM canary должен проверять:

- native function serialization;
- descriptor consistency;
- prototype chains;
- отсутствие неожиданных globals;
- стабильность значений между main frame и worker;
- согласованность iframe realm.

**DoD:**

- Browser стартует headless на всех поддерживаемых ОС.
- После теста нет orphan processes.
- Нет persistent profile между тестами.
- DOM integrity canary проходит без stealth JavaScript injection.
- Browser navigation проходит через WARP egress.

### TB-403: Browser proxy и leak prevention

Настроить native browser prefs для:

- SOCKS host `127.0.0.1`;
- port `40000`;
- SOCKS v5;
- proxy DNS;
- предотвращения direct fallback;
- WebRTC policy.

WebRTC oracle должен различать:

- loopback/private candidates;
- host candidates;
- server-reflexive candidates;
- public direct IP;
- WARP egress;
- mDNS-obfuscated host candidates.

Политика:

- direct public IP вне ожидаемого egress — hard fail;
- private/loopback candidates — фиксируются, но оцениваются по policy;
- отсутствие WebRTC API не должно автоматически считаться fidelity pass;
- отключение WebRTC должно быть частью явно выбранного profile, а не скрытым fallback.

**DoD:**

- Test page не обнаруживает direct public IP.
- DNS unique-host test не попадает в local resolver.
- При остановленном proxy navigation fails closed.
- Browser не переключается на direct connection.

### TB-404: GeoIP alignment

Geo alignment строится по фактическому egress observation:

```text
egress IP
  -> local/self-hosted GeoIP database
  -> country/region/timezone/language candidates
  -> browser launch profile
```

Использовать бесплатную локальную GeoIP-базу с документированной лицензией или конфигурируемый static mapping для тестовой инфраструктуры.

Проверять:

- timezone ↔ egress country/region;
- locale ↔ `Accept-Language`;
- browser language ↔ page language;
- geolocation permission behavior;
- отсутствие одновременно несовместимых timezone/locale/client hints.

Не обещать точность города: GeoIP на уровне city часто неточен.

**DoD:**

- Country/timezone mismatch — hard fail в strict mode.
- City mismatch — informational или policy-driven.
- Запуск не зависит от платного GeoIP API.
- Версия GeoIP database включена в report.

### TB-405: Storage isolation

На каждый тест:

- отдельный temporary profile;
- отдельный cookie jar;
- отдельные localStorage/IndexedDB/cache;
- очистка temp directory;
- запрет reuse профиля по умолчанию.

Добавить сценарий:

1. Run A записывает marker.
2. Run B запускается с новым profile.
3. Marker отсутствует.
4. После завершения profile directories удалены.

**DoD:**

- Нет cross-test cookie/storage contamination.
- Parallel tests не разделяют profile.
- Cleanup выполняется при success, failure и SIGTERM.
- Debug retention возможен только через явный флаг и сопровождается предупреждением о чувствительных данных.

---

# 3. E2E oracle и автоматические тесты

## 3.1. Принцип oracle

`tests/test_e2e_fidelity.py` не должен проверять только HTTP 200. Он должен коррелировать наблюдения одного запуска по `run_id`.

### Обязательные сигналы

| Уровень | Сигнал | Источник | Строгость |
|---|---|---|---|
| Network | WARP egress | collector | hard |
| Network | direct route unchanged | local doctor | hard |
| DNS | proxy-side resolution | unique hostname collector | hard |
| TLS | expected JA4 allowlist | collector | hard |
| TLS | expected ALPN | collector | hard |
| HTTP/2 | profile settings/order | collector | hard/strict |
| Headers | semantic consistency | collector | hard |
| Browser | WARP egress | collector | hard |
| Browser | no direct WebRTC public IP | browser probe | hard |
| Browser | timezone/locale alignment | browser + GeoIP | policy |
| Browser | isolated storage | browser probe | hard |
| DOM | native integrity canaries | browser probe | hard |
| TTL | observed classification | collector | capability-driven |

## 3.2. Статусы oracle

Каждое правило возвращает:

```text
PASS
FAIL
INCONCLUSIVE
UNSUPPORTED
SKIPPED
```

Нельзя сводить всё к произвольному score. Итог:

- любой hard `FAIL` → общий `FAIL`;
- hard `INCONCLUSIVE` → общий `INCONCLUSIVE`, если policy не требует fail-closed;
- optional mismatch снижает informational score, но не скрывает hard failures;
- report всегда содержит evidence.

## 3.3. Структура `tests/test_e2e_fidelity.py`

```python
@pytest.mark.e2e
def test_environment_is_supported(...): ...

@pytest.mark.e2e
def test_default_route_is_unchanged(...): ...

@pytest.mark.e2e
def test_warp_socks_listener_is_loopback_only(...): ...

@pytest.mark.e2e
def test_l7_egress_uses_warp(...): ...

@pytest.mark.e2e
def test_dns_resolution_occurs_through_proxy(...): ...

@pytest.mark.e2e
def test_tls_ja4_matches_pinned_profile(...): ...

@pytest.mark.e2e
def test_http2_profile_matches_golden(...): ...

@pytest.mark.e2e
def test_http_headers_are_coherent(...): ...

@pytest.mark.e2e
def test_browser_egress_matches_l7_egress(...): ...

@pytest.mark.e2e
def test_browser_has_no_direct_webrtc_leak(...): ...

@pytest.mark.e2e
def test_browser_geo_profile_matches_egress(...): ...

@pytest.mark.e2e
def test_browser_storage_is_isolated(...): ...

@pytest.mark.e2e
def test_dom_integrity_canaries(...): ...

@pytest.mark.e2e
def test_proxy_failure_is_fail_closed(...): ...

@pytest.mark.e2e
def test_final_fidelity_report_schema(...): ...
```

## 3.4. Негативные тесты

Обязательны deliberate mismatch tests:

- заменить `socks5h` на `socks5`;
- остановить WARP;
- изменить impersonation profile;
- форсировать HTTP/1.1;
- изменить `User-Agent`;
- запустить browser с direct proxy;
- установить конфликтующий timezone;
- повторно использовать profile directory;
- подложить неправильный collector response;
- передать observation с другим `run_id`;
- изменить signed/golden fixture.

**DoD oracle:**

- Каждый критический detector имеет минимум один negative test.
- Один сигнал не может подтвердить сам себя.
- Client-provided claims не используются как server-side evidence.
- Все отчёты проходят JSON Schema validation.
- Failure output содержит краткую причину и путь к artifact bundle.

---

# 4. Self-hosted fidelity collector

Без собственного collector-а невозможно надёжно проверять JA4, HTTP/2 frame profile и egress observations.

## 4.1. Требования

Collector должен:

- быть open-source;
- запускаться локально или на бесплатной собственной инфраструктуре;
- принимать только низкочастотные probe requests;
- иметь TLS endpoint без промежуточного CDN;
- писать bounded structured logs;
- коррелировать по `run_id`;
- отдавать observation только авторизованному test client;
- поддерживать expiration/retention.

## 4.2. Интерфейсы

```text
GET  /healthz
GET  /v1/probe/http
GET  /v1/probe/browser
POST /v1/browser-observation
GET  /v1/runs/{run_id}
GET  /v1/dns-token/{token}
```

## 4.3. Безопасность

- HMAC-связанный correlation token.
- Rate limit.
- Allowlist test source/environment при необходимости.
- Максимальный размер headers/body.
- Не логировать cookies и authorization.
- Retention по умолчанию, например, 24 часа.
- Collector не должен становиться open proxy.

**DoD:**

- Collector разворачивается одной documented command.
- Есть contract tests между client и collector.
- TLS/HTTP2 observation проверено packet capture-ом.
- Никаких платных компонентов.

---

# 5. Спецификация `scripts/setup.sh`

## 5.1. CLI

```bash
sudo ./scripts/setup.sh \
  --mode minimal|full \
  --warp-port 40000 \
  --non-interactive \
  --json-report /tmp/setup-report.json
```

Дополнительные режимы:

```bash
./scripts/setup.sh --check
./scripts/setup.sh --dry-run
./scripts/setup.sh --repair
./scripts/uninstall.sh --keep-cache
```

## 5.2. Порядок выполнения

1. `set -Eeuo pipefail`.
2. Установка `trap` для отчёта об ошибке.
3. Получение lock через `flock`.
4. Проверка ОС и архитектуры.
5. Проверка свободного места и DNS/connectivity.
6. Снимок:
   - default route;
   - `/etc/resolv.conf`;
   - firewall summary;
   - active SSH connection;
   - WARP status.
7. Установка минимальных dependencies.
8. Добавление repository key в отдельный keyring, не через deprecated global `apt-key`.
9. Установка/pinning WARP package.
10. Запуск vendor daemon.
11. Registration и proxy configuration.
12. Проверка loopback listener.
13. Установка Python package в venv/`uv` environment.
14. При `full` — загрузка browser artifact с checksum.
15. Запуск smoke tests.
16. Сравнение network snapshot.
17. Запись machine-readable manifest.

## 5.3. Запрещённые действия

Скрипт не должен:

- выполнять `ufw reset`;
- очищать `iptables`/`nftables`;
- менять SSH port;
- менять `/etc/ssh/sshd_config`;
- включать WARP full-tunnel mode по умолчанию;
- менять default route;
- менять глобальный DNS;
- применять глобальный TTL;
- удалять неизвестные пакеты;
- использовать `curl | bash` без checksum/signature control.

## 5.4. Setup performance budget

Пример бюджета для `minimal`:

| Этап | Бюджет |
|---|---:|
| Preflight | 3 сек |
| apt metadata/package install | 20 сек |
| WARP installation/start | 15 сек |
| Python artifact install | 10 сек |
| Configuration | 5 сек |
| Smoke | 7 сек |
| **Итого** | **60 сек** |

Для достижения SLA:

- использовать prebuilt wheels;
- не выполнять source compilation;
- не обновлять все системные пакеты;
- не делать полный `apt upgrade`;
- кешировать release artifacts;
- выпускать единый versioned bundle;
- измерять `p50`, `p95`, max отдельно.

**DoD setup:**

- p95 `<60 сек` на утверждённой матрице для `minimal`.
- Full mode имеет отдельный опубликованный SLA.
- Setup повторяем и идемпотентен.
- В CI присутствует тест на сохранность default route.
- Есть clean uninstall и inventory установленных файлов.

---

# 6. Тестовая стратегия и CI

## 6.1. Уровни

### Unit

- parsing WARP CLI;
- config validation;
- profile compatibility;
- header policy;
- scoring/rules;
- schema serialization;
- redaction.

### Contract

- client ↔ collector;
- report JSON Schema;
- browser probe payload;
- version manifest.

### Integration

- local SOCKS stub;
- DNS token service;
- real `curl_cffi`;
- collector in container;
- browser startup in virtual display/headless.

### E2E privileged

- реальный WARP daemon;
- owned remote collector;
- Ubuntu/Debian clean VM;
- reboot persistence;
- proxy fail-closed;
- SSH-safe setup.

## 6.2. CI jobs

```text
lint
typecheck
unit
contract
integration-curl
integration-browser
shellcheck
systemd-verify
security-scan
package
e2e-ubuntu-22.04
e2e-ubuntu-24.04
e2e-debian-12
setup-performance
uninstall-verification
```

## 6.3. Инструменты качества

- `ruff`;
- `mypy` или `pyright`;
- `pytest`;
- `pytest-xdist` только для изолированных тестов;
- `shellcheck`;
- `shfmt`;
- `systemd-analyze verify`;
- `pip-audit`/эквивалент;
- secret scanning;
- SBOM для release bundle;
- pinned lockfile.

## 6.4. Flake policy

Сетевой тест не перезапускается бесконечно.

- максимум один retry только для явно transient transport error;
- fidelity mismatch не retry-ится автоматически;
- все retries записываются в report;
- flaky test считается дефектом;
- quarantine имеет owner и deadline.

---

# 7. Research-документы

Каждый research document должен содержать:

1. вопрос;
2. гипотезы;
3. экспериментальный стенд;
4. версии компонентов;
5. команды воспроизведения;
6. raw evidence;
7. вывод;
8. ограничения;
9. принятое решение;
10. impact на implementation/tests.

---

## `research/01-network-warp-socks-ttl.md`

### Темы

- Поведение WARP proxy mode.
- Возможность фиксировать порт `40000`.
- Семантика DNS через SOCKS5.
- Отличие `socks5` и `socks5h`.
- Кто создаёт внешний TCP flow.
- Какой TTL наблюдается collector-ом.
- Можно ли и где контролировать TTL.
- Поведение при рестарте daemon.
- Binding только на loopback.
- Поведение IPv4/IPv6.
- Fail-open/fail-closed.

### Обязательные эксперименты

- packet capture на loopback;
- direct request vs WARP request;
- unique DNS hostname;
- daemon stop mid-session;
- reboot;
- concurrent clients;
- port conflict;
- unsupported WARP version.

### Результат

Чёткое решение: TTL является:

- enforceable;
- observable-only;
- либо unsupported в текущей архитектуре.

---

## `research/02-tls-ja4-http2.md`

### Темы

- Версии `curl_cffi` и TLS backend.
- Реальные ClientHello profiles.
- JA4 stability.
- GREASE.
- HTTP/2 SETTINGS ordering.
- Pseudo-header ordering.
- Header casing.
- Connection reuse.
- Различия HTTP/1.1 и HTTP/2.
- Collector implementation options.

### Обязательные артефакты

- pcap;
- decoded ClientHello;
- canonical JA4;
- H2 frame trace;
- golden observation JSON;
- compatibility table по версиям.

### Результат

Versioned L7 profiles и процедура безопасного upgrade.

---

## `research/03-camoufox-gecko-integrity.md`

### Темы

- Точная архитектура Camoufox.
- Где применяются native patches, а где config.
- Headless/headed differences.
- Proxy DNS.
- WebRTC behavior.
- Timezone/locale configuration.
- Worker/iframe consistency.
- Storage paths.
- Crash cleanup.
- Artifact size и setup SLA.

### Обязательные эксперименты

- main frame vs worker;
- iframe realm;
- WebRTC candidates;
- DNS unique hostname;
- storage reuse;
- process cleanup;
- cold/warm startup;
- browser artifact verification.

### Результат

Подтверждённый native-first browser profile без page JS spoofing.

---

## `research/04-e2e-oracle-threat-model.md`

### Темы

- Что считается fidelity.
- Какие наблюдения client-controlled.
- Какие server-controlled.
- Возможность подделки report.
- Correlation token.
- Replay protection.
- Collector TLS topology.
- Retention и privacy.
- False positive/false negative taxonomy.
- Hard и soft rules.

### Threat model

Учитывать:

- подмену collector response;
- случайный direct fallback;
- DNS leak;
- profile version drift;
- stale browser artifact;
- смешивание run IDs;
- прокси/CDN перед collector;
- логирование секретов;
- flaky GeoIP;
- недостоверность city-level GeoIP;
- невозможность точного TTL inference.

### Результат

Формальная модель доверия и policy evaluation.

---

# 8. Документация

## 8.1. `README.md`

Должен отвечать за 2–3 минуты:

- что делает проект;
- чего проект не делает;
- поддерживаемые ОС;
- quickstart;
- expected output;
- ссылка на architecture и troubleshooting;
- legal/authorized-use note.

## 8.2. `docs/quickstart.md`

Сценарий:

```bash
git clone ...
cd stealth-core
sudo ./scripts/setup.sh --mode minimal --non-interactive
stealth-core doctor
pytest -m e2e tests/test_e2e_fidelity.py
```

Для каждой команды показать:

- expected duration;
- expected output;
- common failure;
- rollback.

## 8.3. `docs/architecture.md`

Содержит:

- C4 context/container/component diagrams;
- data flow;
- trust boundaries;
- collector topology;
- proxy/DNS flow;
- artifacts lifecycle;
- versioning model.

## 8.4. `docs/fidelity-model.md`

Определяет:

- profile;
- observation;
- rule;
- evidence;
- hard/soft requirement;
- unsupported/inconclusive;
- final report semantics.

## 8.5. `docs/troubleshooting.md`

Минимальные разделы:

- WARP daemon not running;
- registration failure;
- port 40000 occupied;
- SOCKS connects but target fails;
- DNS leak;
- JA4 mismatch after upgrade;
- H2 fallback;
- Camoufox artifact missing;
- browser crash;
- WebRTC direct IP;
- GeoIP mismatch;
- setup exceeded 60 seconds;
- SSH safety verification.

## 8.6. ADR

Все существенные решения оформляются до стабилизации API:

- no global route mutation;
- no global TTL mutation;
- owned collector;
- profile pinning;
- ephemeral browser profiles;
- no JavaScript fingerprint patching;
- status semantics;
- setup SLA assumptions.

**DoD документации:**

- Все команды запускаются в docs CI.
- Нет ссылок на несуществующие файлы.
- Версии и filenames совпадают с release.
- Troubleshooting содержит диагностические команды, а не совет «переустановить сервер».

---

# 9. Финальный `SKILL.md`

## 9.1. Назначение

Skill должен позволять агенту безопасно:

- проверить prerequisites;
- установить контур;
- диагностировать WARP/SOCKS;
- запустить L7 probe;
- запустить browser probe;
- интерпретировать fidelity report;
- не выполнить разрушительные сетевые изменения;
- собрать redacted diagnostic bundle.

## 9.2. Требования к содержанию

Предлагаемый каркас:

```markdown
---
name: stealth-core
description: >
  Install, validate, and operate the zero-cost VPN/SUM fidelity test
  environment using WARP SOCKS5h, curl_cffi, Camoufox, and the
  self-hosted fidelity oracle.
---

# Stealth Core

## When to use

## When not to use

## Safety invariants

## Repository discovery

## Supported environments

## Fast path

## Installation workflow

## Network validation workflow

## L7 fidelity workflow

## Browser E2E workflow

## Interpreting the oracle

## Failure classification

## Troubleshooting decision tree

## Cleanup and uninstall

## Evidence and reporting requirements

## Commands that are prohibited by default
```

## 9.3. Обязательные инструкции агенту

Агент должен:

1. Сначала прочитать `AGENTS.md`, `context.md`, `prompt.md`.
2. Проверить `git status`.
3. Не перезаписывать пользовательские изменения.
4. Не менять default route.
5. Не трогать SSH.
6. Не сбрасывать firewall.
7. Не применять global TTL.
8. Использовать `socks5h`.
9. Не объявлять JA4/H2 pass без server-side evidence.
10. Не объявлять DNS/WebRTC leak-free без dedicated tests.
11. Не логировать секреты.
12. После изменения запускать релевантный узкий тест, затем полный suite.
13. При невозможности проверки возвращать `inconclusive/unsupported`.
14. Показывать пользователю изменённые файлы, команды и результаты тестов.

## 9.4. Decision tree

```text
Is OS supported?
  no  -> stop: unsupported
  yes
    Is warp-svc healthy?
      no -> repair vendor service
      yes
        Is 127.0.0.1:40000 listening?
          no -> reconcile proxy mode
          yes
            Does SOCKS5h probe pass?
              no -> classify DNS/connect/egress error
              yes
                Does L7 oracle pass?
                  no -> inspect profile/version/collector
                  yes
                    Does browser oracle pass?
                      no -> inspect proxy/WebRTC/geo/storage
                      yes -> emit final fidelity report
```

## 9.5. Проверка skill

Создать scripted scenarios:

- clean successful install;
- WARP missing;
- port conflict;
- direct route accidentally changed;
- JA4 mismatch;
- DNS leak;
- browser artifact mismatch;
- WebRTC leak;
- storage contamination;
- unsupported OS.

**DoD SKILL:**

- Новый агент способен пройти happy path без скрытого контекста.
- Агент не предлагает destructive network commands.
- Все упомянутые команды существуют.
- Skill различает failure и unsupported.
- Skill проверен минимум на одном чистом окружении другим исполнителем.

---

# 10. Release engineering

## 10.1. Version manifest

Каждый release должен содержать:

```json
{
  "stealth_core": "x.y.z",
  "warp_supported_versions": [],
  "curl_cffi": "...",
  "impersonation_profiles": [],
  "camoufox": "...",
  "gecko": "...",
  "collector": "...",
  "geoip_database": "...",
  "schemas": {
    "observation": "1.0",
    "report": "1.0"
  }
}
```

## 10.2. Release artifacts

- Python wheel.
- Source tarball.
- Browser artifact manifest/checksums.
- SBOM.
- Checksums.
- Changelog.
- Golden observations.
- Setup performance report.
- Compatibility matrix.

## 10.3. Upgrade policy

Любое обновление WARP, `curl_cffi` или Camoufox требует:

1. compatibility job;
2. fresh collector evidence;
3. comparison с golden profile;
4. review расхождений;
5. обновление research/ADR, если изменился протокол;
6. canary release;
7. только затем изменение default profile.

---

# 11. Definition of Done по этапам

## Этап A — Foundation

- [ ] Контекст проекта проаудирован.
- [ ] Все требования трассируются до тестов.
- [ ] Определены JSON schemas.
- [ ] Зафиксирована compatibility matrix.
- [ ] CI запускает lint/unit/contract.

## Этап B — Network

- [ ] WARP устанавливается идемпотентно.
- [ ] Proxy слушает `127.0.0.1:40000`.
- [ ] Default route не меняется.
- [ ] SSH не затрагивается.
- [ ] SOCKS5h и remote DNS доказаны.
- [ ] Есть reboot persistence.
- [ ] TTL не получает ложный pass.
- [ ] Setup/uninstall протестированы.

## Этап C — L7

- [ ] `curl_cffi` и profile version pinned.
- [ ] JA4 наблюдается на collector-е.
- [ ] ALPN проверяется.
- [ ] HTTP/2 SETTINGS/pseudo-header policy проверяется.
- [ ] Header coherence проверяется.
- [ ] Negative mismatch tests успешно обнаруживают ошибки.

## Этап D — Browser

- [ ] Camoufox artifact pinned и checksum-verified.
- [ ] Proxy configured до первой навигации.
- [ ] Direct fallback блокируется.
- [ ] DNS leak отсутствует.
- [ ] Direct public WebRTC IP отсутствует.
- [ ] Geo/timezone/locale согласованы согласно policy.
- [ ] Storage изолирован.
- [ ] Нет orphan processes.
- [ ] DOM integrity canaries проходят.

## Этап E — Oracle

- [ ] Все observation contracts versioned.
- [ ] Hard/soft rules формализованы.
- [ ] `PASS/FAIL/INCONCLUSIVE/UNSUPPORTED` реализованы.
- [ ] Корреляция по `run_id` защищена.
- [ ] Client claims не считаются server evidence.
- [ ] `tests/test_e2e_fidelity.py` проверяет полный путь.
- [ ] Diagnostic bundle создаётся с redaction.

## Этап F — Setup SLA

- [ ] Определены эталонные VPS images.
- [ ] Определены network assumptions.
- [ ] Minimal setup p95 `<60 сек`.
- [ ] Full setup SLA опубликован отдельно.
- [ ] Нет source compilation на hot path.
- [ ] Результаты benchmark доступны как release artifact.

## Этап G — Docs и Skill

- [ ] README и quickstart проверены на чистой машине.
- [ ] Research 01–04 содержат воспроизводимые evidence.
- [ ] ADR отражают ключевые решения.
- [ ] `SKILL.md` не содержит несуществующих команд.
- [ ] Skill проверен независимым агентом.
- [ ] Troubleshooting покрывает все основные failure modes.

---

# 12. Финальный релизный gate

Репозиторий считается эталонным только если одна команда:

```bash
sudo ./scripts/setup.sh --mode minimal --non-interactive \
  && stealth-core doctor \
  && pytest -m e2e tests/test_e2e_fidelity.py
```

даёт:

1. успешный, schema-valid setup report;
2. неизменный default route;
3. активный loopback-only SOCKS proxy;
4. подтверждённый WARP egress;
5. отсутствие DNS leak;
6. server-observed JA4 из разрешённого versioned profile;
7. ожидаемый ALPN и HTTP/2 profile;
8. согласованные L7 headers;
9. browser egress, совпадающий с сетевым профилем;
10. отсутствие direct WebRTC public IP;
11. согласованный geo/locale/timezone профиль;
12. storage isolation;
13. DOM integrity pass;
14. честный TTL status;
15. итоговый `FidelityReport` с evidence и точными версиями.

Любое из следующего блокирует релиз:

- неподтверждённый JA4;
- использование client-side самоотчёта вместо collector evidence;
- direct DNS/WebRTC leak;
- изменение default route;
- глобальная модификация TTL;
- неидемпотентный setup;
- скрытый fallback на direct connection;
- persistent browser profile;
- незапиненные browser/TLS artifacts;
- тест, который превращает `unsupported` в `pass`;
- зависимость обязательного контура от платного сервиса.

---

# 13. Рекомендуемый порядок исполнения

1. **TB-000–002:** аудит, контракты, capability matrix.
2. **TB-101–103:** минимальный работающий WARP/SOCKS/collector tracer bullet.
3. **TB-201–204:** hardening сети, DNS и честное решение по TTL.
4. **TB-301–304:** один полностью подтверждённый L7 profile.
5. **TB-401–405:** browser path, leaks, geo и storage.
6. **Oracle:** объединение evidence и negative tests.
7. **Setup performance:** release bundle и доказательство SLA.
8. **Research/ADR/docs:** полировка и фиксация воспроизводимости.
9. **SKILL.md:** операционный workflow поверх уже существующих и проверенных команд.
10. **Independent clean-room validation:** запуск человеком или агентом, который не участвовал в реализации.

Главный принцип реализации: сначала один честный вертикальный путь с server-side evidence, затем расширение профилей и оптимизация. Нельзя начинать с декларации «100% coherence» — эта характеристика должна быть результатом измеримых независимых проверок на каждом уровне стека.