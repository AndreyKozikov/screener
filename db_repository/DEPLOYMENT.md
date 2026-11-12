# Развёртывание db_repository на Ubuntu/Debian

Документ описывает установку микросервиса `db_repository` на отдельный сервер под управлением Ubuntu 22.04/24.04 или Debian 12, запуск через systemd с автоматическим стартом и перезапуском при падении, а также настройку самого сервиса и клиентов.

## 1. Схема размещения

Рекомендуемая структура каталогов:

```text
/opt/bondscreener/
├── venv/                          # виртуальное окружение Python
└── db_repository/                 # код микросервиса
    ├── config/
    │   └── config.toml            # несекретная конфигурация (создаётся на сервере)
    ├── .env                       # секреты (создаётся на сервере)
    ├── data/
    │   └── db/
    │       ├── bonds.db
    │       ├── blog.db
    │       ├── history_db.db
    │       └── portfolios.db
    └── logs/                      # файловые логи сервиса
```

Важно: `db_repository` импортируется как пакет `db_repository`, поэтому рабочий каталог службы — `/opt/bondscreener`, а не `/opt/bondscreener/db_repository`.

## 2. Требования

- Ubuntu 22.04/24.04 или Debian 12.
- Python 3.11 или новее: код использует `tomllib`.
- Не менее 2 ГБ свободного места под код, окружение и SQLite-файлы (объём зависит от `history_db.db`).
- Доступ с `sudo`.
- SQLite-файлы должны лежать на локальном диске. Не размещайте их на NFS/SMB: блокировки SQLite в таких файловых системах ненадёжны.

Проверьте версию Python:

```bash
python3 --version
```

Если версия ниже 3.11:

- Debian 12: штатный `python3` уже 3.11, установите `python3 python3-venv python3-pip`.
- Ubuntu 24.04: штатный `python3` уже 3.12.
- Ubuntu 22.04: установите Python 3.11 из PPA `deadsnakes`:

```bash
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv
```

## 3. Подготовка сервера

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip sqlite3 rsync curl ca-certificates
```

Для Ubuntu 22.04 с Python 3.11 замените `python3` на `python3.11` в командах создания venv.

## 4. Пользователь и каталоги

Создайте системного пользователя без интерактивного входа:

```bash
sudo useradd --system --create-home --home-dir /opt/bondscreener --shell /usr/sbin/nologin bondscreener
```

Создайте каталоги и выставьте права:

```bash
sudo mkdir -p /opt/bondscreener/db_repository/data/db
sudo mkdir -p /opt/bondscreener/db_repository/logs
sudo chown -R bondscreener:bondscreener /opt/bondscreener
sudo chmod 750 /opt/bondscreener /opt/bondscreener/db_repository
sudo chmod 750 /opt/bondscreener/db_repository/data /opt/bondscreener/db_repository/data/db
sudo chmod 750 /opt/bondscreener/db_repository/logs
```

## 5. Копирование кода

Скопируйте только код микросервиса. Не копируйте `.env`, реальный `config/config.toml`, `__pycache__`, `.idea` и локальные БД.

Пример с машины разработчика:

```bash
rsync -av \
  --exclude '__pycache__' \
  --exclude '.idea' \
  --exclude '.env' \
  --exclude 'config/config.toml' \
  --exclude 'data' \
  --exclude 'logs' \
  db_repository/ user@db-host:/tmp/db_repository/
```

На сервере:

```bash
sudo rsync -a /tmp/db_repository/ /opt/bondscreener/db_repository/
sudo chown -R bondscreener:bondscreener /opt/bondscreener/db_repository
```

Если код доставляется через git, клонируйте репозиторий и скопируйте каталог `db_repository` в `/opt/bondscreener/db_repository`.

## 6. Виртуальное окружение и зависимости

Создайте venv от нужной версии Python. Для Debian 12 и Ubuntu 24.04:

```bash
sudo -u bondscreener python3 -m venv /opt/bondscreener/venv
```

Для Ubuntu 22.04 с Python 3.11:

```bash
sudo -u bondscreener python3.11 -m venv /opt/bondscreener/venv
```

Установите зависимости:

```bash
sudo -u bondscreener /opt/bondscreener/venv/bin/python -m pip install --upgrade pip
sudo -u bondscreener /opt/bondscreener/venv/bin/python -m pip install -r /opt/bondscreener/db_repository/requirements.txt
```

Если для вашей архитектуры нет готовых wheel-пакетов и pip начинает собирать зависимости из исходников, установите инструменты сборки:

```bash
sudo apt install -y build-essential python3-dev
```

Проверьте импорт и синтаксис:

```bash
cd /opt/bondscreener
sudo -u bondscreener PYTHONPATH=/opt/bondscreener \
  /opt/bondscreener/venv/bin/python -c "import db_repository.main_db; print('import ok')"
```

Единственный лаунчер сервиса — `db_repository/run_db_service.py`:

- из PyCharm: Python Run Configuration со script path `/opt/bondscreener/db_repository/run_db_service.py`;
- как модуль: `python -m db_repository.run_db_service`;
- как systemd: `ExecStart=/opt/bondscreener/venv/bin/python -m db_repository.run_db_service`.

`db_repository/main_db.py` — только ASGI-модуль с переменной `app`, отдельным лаунчером он не является.

## 7. Настройка микросервиса

### 7.1. config/config.toml

Создайте `/opt/bondscreener/db_repository/config/config.toml`.

Вариант для backend и conversion_service на том же сервере (сервис слушает только localhost):

```toml
[server]
host = "127.0.0.1"
port = 8964
workers = 1
reload = false
log_level = "info"
run_migrations_on_startup = true

[security]
require_api_key = true

[paths]
db_dir = "/opt/bondscreener/db_repository/data/db"
data_dir = "/opt/bondscreener/db_repository/data"
log_dir = "/opt/bondscreener/db_repository/logs"
db_filename = "bonds.db"
blog_db_filename = "blog.db"
history_db_filename = "history_db.db"
portfolio_db_filename = "portfolios.db"

[database]
sqlite_busy_timeout_ms = 30000
```

Вариант для доступа с других хостов по приватной сети:

```toml
[server]
host = "0.0.0.0"
```

В этом случае обязательно ограничьте доступ firewall или поставьте reverse proxy с TLS. Не открывайте `8964` в интернет без TLS.

Пояснения:

- `workers = 1` — обязательное значение для SQLite. Несколько процессов на одной SQLite-БД повышают риск блокировок.
- `reload = false` — обязательно для эксплуатации.
- `run_migrations_on_startup = true` — при первом запуске применит миграции всех четырёх БД. После успешного ввода в эксплуатацию можно поставить `false` и применять миграции отдельной командой (см. раздел 9).
- `require_api_key = true` — при пустом `DB_REPOSITORY_API_KEY` сервис отвечает отказом (fail-closed).
- `db_dir`, `data_dir`, `log_dir` можно задавать абсолютными путями; сервис не зависит от `backend/`.

Выставьте права:

```bash
sudo chown root:bondscreener /opt/bondscreener/db_repository/config/config.toml
sudo chmod 640 /opt/bondscreener/db_repository/config/config.toml
```

### 7.2. .env

Сгенерируйте ключ и создайте `/opt/bondscreener/db_repository/.env`:

```bash
API_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
sudo tee /opt/bondscreener/db_repository/.env >/dev/null <<EOF
DB_REPOSITORY_API_KEY=${API_KEY}
EOF
unset API_KEY
```

Выставьте права:

```bash
sudo chown bondscreener:bondscreener /opt/bondscreener/db_repository/.env
sudo chmod 600 /opt/bondscreener/db_repository/.env
```

Тот же ключ должен быть в `.env` backend и conversion_service. Не храните ключ в `config.toml` и не коммитьте его в git.

## 8. Перенос SQLite-файлов

Остановите старый сервис или процесс, который писал в БД. Для получения согласованной копии используйте `sqlite3 .backup`, а не простое копирование файла.

На старом сервере:

```bash
sqlite3 /path/to/bonds.db ".backup '/tmp/bonds.db'"
sqlite3 /path/to/blog.db ".backup '/tmp/blog.db'"
sqlite3 /path/to/history_db.db ".backup '/tmp/history_db.db'"
sqlite3 /path/to/portfolios.db ".backup '/tmp/portfolios.db'"
```

Если файлы находятся в режиме WAL, предварительно выполните:

```bash
sqlite3 /path/to/bonds.db "PRAGMA wal_checkpoint(TRUNCATE);"
```

Скопируйте файлы на новый сервер:

```bash
sudo install -o bondscreener -g bondscreener -m 600 /tmp/bonds.db /opt/bondscreener/db_repository/data/db/bonds.db
sudo install -o bondscreener -g bondscreener -m 600 /tmp/blog.db /opt/bondscreener/db_repository/data/db/blog.db
sudo install -o bondscreener -g bondscreener -m 600 /tmp/history_db.db /opt/bondscreener/db_repository/data/db/history_db.db
sudo install -o bondscreener -g bondscreener -m 600 /tmp/portfolios.db /opt/bondscreener/db_repository/data/db/portfolios.db
```

Проверьте целостность:

```bash
for db in bonds blog history_db portfolios; do
  sqlite3 "/opt/bondscreener/db_repository/data/db/${db}.db" "PRAGMA integrity_check;"
done
```

Ожидаемый результат — `ok` для каждой БД.

Если БД ещё нет и вы хотите создать пустые, просто оставьте каталог `data/db` пустым: миграции при старте создадут файлы и схему.

## 9. Миграции

### Вариант A: автоматически при старте

В `config.toml` установите:

```toml
[server]
run_migrations_on_startup = true
```

При запуске службы выполнятся миграции `bonds`, `blog`, `history_db`, `portfolios`.

### Вариант B: вручную

Установите `run_migrations_on_startup = false`, остановите службу и выполните:

```bash
sudo systemctl stop bondscreener-db
cd /opt/bondscreener
sudo -u bondscreener PYTHONPATH=/opt/bondscreener \
  /opt/bondscreener/venv/bin/python -c "
from db_repository.core.migrations import (
    run_migrations,
    run_blog_migrations,
    run_history_migrations,
    run_portfolio_migrations,
)
run_migrations()
run_blog_migrations()
run_history_migrations()
run_portfolio_migrations()
print('migrations complete')
"
sudo systemctl start bondscreener-db
```

Перед миграциями сделайте резервную копию `data/db`.

## 10. systemd-служба

Создайте `/etc/systemd/system/bondscreener-db.service`:

```ini
[Unit]
Description=BondsScreener database repository
Documentation=file:///opt/bondscreener/db_repository/DEPLOYMENT.md
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=bondscreener
Group=bondscreener
WorkingDirectory=/opt/bondscreener
Environment=PYTHONPATH=/opt/bondscreener
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/opt/bondscreener/venv/bin/python -m db_repository.run_db_service
Restart=always
RestartSec=5
TimeoutStopSec=30
KillSignal=SIGINT
LimitNOFILE=65536
UMask=0077

# Ограничение прав
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
ReadWritePaths=/opt/bondscreener/db_repository/data /opt/bondscreener/db_repository/logs

[Install]
WantedBy=multi-user.target
```

Пояснения:

- `ExecStart` использует `run_db_service`, поэтому host/port/workers/reload берутся из `config.toml`.
- `Restart=always` и `RestartSec=5` обеспечивают перезапуск при падении и после завершения процесса.
- `StartLimitIntervalSec=0` отключает ограничение количества перезапусков. Если сервис падает циклически, смотрите журнал; при необходимости задайте `StartLimitBurst` и `StartLimitIntervalSec` для защиты от бесконечного цикла.
- `ProtectSystem=strict` делает `/opt` read-only. Запись разрешена только в `ReadWritePaths`: `data` и `logs`. Поэтому каталоги должны существовать до запуска.
- `UMask=0077` не даёт создавать файлы, доступные другим пользователям.
- `KillSignal=SIGINT` даёт uvicorn возможность корректно завершиться.

Примените конфигурацию:

```bash
sudo systemctl daemon-reload
```

## 11. Запуск и автозагрузка

Включите службу в автозагрузку и запустите:

```bash
sudo systemctl enable --now bondscreener-db
```

Проверьте состояние:

```bash
sudo systemctl status bondscreener-db --no-pager
```

Проверьте, что порт слушается:

```bash
ss -ltnp | grep 8964
```

Проверьте health:

```bash
curl -fsS http://127.0.0.1:8964/health
```

Ожидаемый ответ:

```json
{"status":"healthy"}
```

Проверьте readiness с ключом:

```bash
DB_KEY="$(sudo grep '^DB_REPOSITORY_API_KEY=' /opt/bondscreener/db_repository/.env | cut -d= -f2-)"
curl -fsS -H "X-API-Key: ${DB_KEY}" http://127.0.0.1:8964/ready
unset DB_KEY
```

Ожидаемый ответ:

```json
{"status":"ready"}
```

Если `ready` возвращает `503`, в ответе будут перечислены отсутствующие файлы БД или неприменённые миграции.

## 12. Проверка автоматического перезапуска

Убедитесь, что служба поднимается после принудительного завершения:

```bash
sudo systemctl kill -s SIGKILL bondscreener-db
sleep 6
sudo systemctl is-active bondscreener-db
```

Ожидается `active`. Дополнительно проверьте автозапуск после перезагрузки:

```bash
sudo reboot
```

После перезагрузки:

```bash
sudo systemctl is-enabled bondscreener-db
sudo systemctl is-active bondscreener-db
curl -fsS http://127.0.0.1:8964/health
```

## 13. Сеть, firewall и TLS

### 13.1. Backend и conversion_service на том же сервере

Оставьте в `config.toml`:

```toml
[server]
host = "127.0.0.1"
```

Порт `8964` не должен быть доступен извне. Firewall не требуется для этого порта.

### 13.2. Backend и conversion_service на других серверах

Разрешите порт только для IP клиентов. Пример для UFW:

```bash
sudo ufw allow from 10.0.0.10 to any port 8964 proto tcp
sudo ufw allow from 10.0.0.11 to any port 8964 proto tcp
sudo ufw reload
```

Если серверы находятся в разных сетях или трафик идёт через интернет, используйте TLS/reverse proxy. Пример nginx:

```nginx
server {
    listen 443 ssl http2;
    server_name db.example.com;

    ssl_certificate     /etc/letsencrypt/live/db.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/db.example.com/privkey.pem;

    client_max_body_size 1m;

    location / {
        proxy_pass http://127.0.0.1:8964;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
}
```

При использовании nginx оставьте `host = "127.0.0.1"` в `config.toml` и откройте только `443`.

## 14. Настройка клиентов

Ключ `DB_REPOSITORY_API_KEY` должен совпадать на сервере БД, в backend и в conversion_service.

### 14.1. backend

В `backend/config/config.toml`:

```toml
[db_repository]
url = "https://db.example.com"
timeout_seconds = 300.0
connect_timeout_seconds = 10.0
verify_tls = true
ca_bundle = ""
max_retries = 2
```

Если используется внутренний CA или самоподписанный сертификат:

```toml
ca_bundle = "/etc/ssl/certs/internal-ca.pem"
```

В `backend/.env`:

```dotenv
DB_REPOSITORY_API_KEY=<тот же ключ>
```

### 14.2. conversion_service

В `conversion_service/config/config.toml`:

```toml
[db_repository]
url = "https://db.example.com"
timeout_seconds = 300.0
connect_timeout_seconds = 10.0
verify_tls = true
ca_bundle = ""
max_retries = 2
```

В `conversion_service/.env`:

```dotenv
DB_REPOSITORY_API_KEY=<тот же ключ>
AUTH_SECRET_KEY=<тот же AUTH_SECRET_KEY, что в backend/.env>
```

После изменения конфигурации перезапустите backend и conversion_service.

## 15. Обновление и откат

### Обновление

```bash
sudo systemctl stop bondscreener-db

# Резервная копия БД
sudo mkdir -p /var/backups/bondscreener
sudo sqlite3 /opt/bondscreener/db_repository/data/db/bonds.db \
  ".backup '/var/backups/bondscreener/bonds-$(date +%F-%H%M%S).db'"

# Доставка нового кода и зависимостей
sudo rsync -a \
  --exclude '__pycache__' \
  --exclude '.idea' \
  --exclude '.env' \
  --exclude 'config/config.toml' \
  --exclude 'data' \
  --exclude 'logs' \
  /tmp/db_repository/ /opt/bondscreener/db_repository/
sudo chown -R bondscreener:bondscreener /opt/bondscreener/db_repository
sudo -u bondscreener /opt/bondscreener/venv/bin/python -m pip install -r /opt/bondscreener/db_repository/requirements.txt

sudo systemctl start bondscreener-db
sudo systemctl status bondscreener-db --no-pager
```

Если обновление содержит миграции, выполните их по разделу 9 до запуска службы или оставьте `run_migrations_on_startup = true`.

### Откат

```bash
sudo systemctl stop bondscreener-db
sudo cp -a /path/to/previous/db_repository /opt/bondscreener/
sudo cp -a /var/backups/bondscreener/bonds-<timestamp>.db \
  /opt/bondscreener/db_repository/data/db/bonds.db
sudo chown -R bondscreener:bondscreener /opt/bondscreener/db_repository
sudo systemctl start bondscreener-db
```

## 16. Логи и резервное копирование

### Логи

Логи systemd:

```bash
sudo journalctl -u bondscreener-db -f
sudo journalctl -u bondscreener-db --since "1 hour ago"
```

Файловые логи сервиса находятся в `/opt/bondscreener/db_repository/logs`.

Ротация (необязательно), `/etc/logrotate.d/bondscreener-db`:

```text
/opt/bondscreener/db_repository/logs/*.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    copytruncate
}
```

### Резервное копирование SQLite

Для согласованной копии используйте `.backup`, а не `cp`:

```bash
sudo mkdir -p /var/backups/bondscreener
for db in bonds blog history_db portfolios; do
  sudo sqlite3 "/opt/bondscreener/db_repository/data/db/${db}.db" \
    ".backup '/var/backups/bondscreener/${db}-$(date +%F).db'"
done
```

Резервные копии должны храниться вне сервера. Не запускайте копирование через `cp` при активной записи.

## 17. Диагностика

| Симптом | Причина | Действие |
|---|---|---|
| `401 Invalid API key` | Ключ клиента не совпадает с `db_repository/.env` | Сверьте `DB_REPOSITORY_API_KEY` во всех `.env`, перезапустите клиентов и сервис БД |
| `503 API key is not configured` | `require_api_key=true`, но ключ пуст | Заполните `db_repository/.env`, перезапустите службу |
| `/ready` возвращает `503` | Нет файла БД или не применены миграции | Проверьте `data/db`, выполните миграции, изучите `journalctl` |
| Служба не стартует | Ошибка конфигурации, прав или импорта | `sudo systemctl status bondscreener-db` и `sudo journalctl -u bondscreener-db -n 100` |
| `database is locked` | Несколько процессов/воркеров или внешняя блокировка | Оставьте `workers=1`, остановите лишние процессы, проверьте NFS/SMB |
| Нет доступа к `/opt/.../logs` | Каталог не создан или не в `ReadWritePaths` | Создайте каталог, проверьте права и unit-файл |
| Клиент не подключается по HTTPS | Неверный CA или `verify_tls` | Укажите `ca_bundle` или отключите проверку только в тестовой среде |

Полезные команды:

```bash
sudo systemctl status bondscreener-db --no-pager
sudo journalctl -u bondscreener-db -n 200 --no-pager
sudo systemctl restart bondscreener-db
sudo systemctl daemon-reload
ss -ltnp | grep 8964
```

## 18. Чек-лист ввода в эксплуатацию

- [ ] Python 3.11+ и venv созданы.
- [ ] Зависимости установлены из `db_repository/requirements.txt`.
- [ ] `config/config.toml` создан, `reload=false`, `workers=1`, `require_api_key=true`.
- [ ] `db_repository/.env` содержит сгенерированный `DB_REPOSITORY_API_KEY`, права `600`.
- [ ] SQLite-файлы перенесены через `.backup`, `PRAGMA integrity_check` возвращает `ok`.
- [ ] Каталоги `data` и `logs` принадлежат `bondscreener`, доступны для записи.
- [ ] Миграции применены (автоматически или вручную).
- [ ] systemd-служба включена: `systemctl is-enabled bondscreener-db` → `enabled`.
- [ ] `GET /health` возвращает 200.
- [ ] `GET /ready` с `X-API-Key` возвращает 200.
- [ ] Проверен перезапуск после `SIGKILL` и после `reboot`.
- [ ] Порт ограничен localhost или firewall; при внешнем доступе настроен TLS.
- [ ] Ключ продублирован в `backend/.env` и `conversion_service/.env`.
- [ ] Настроены резервное копирование и ротация логов.
