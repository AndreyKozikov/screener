# Руководство по развертыванию BondsScreener на Debian (Bare-metal, без Docker)

Данное руководство описывает полностью настроенный процесс развертывания проекта на чистом сервере **Debian** с автоматическим деплоем через **GitHub Actions**.

---

## Архитектура развертывания

- **Без Docker:** все компоненты работают нативно под управлением `systemd`.
- **Без привязки к конкретному IP:** 
  - Nginx слушает `server_name _;` и принимает запросы на 80 порту по любому IP или хосту.
  - Фронтенд обращается к бэкенду по относительным путям `/api` и `/conversion-api`.
  - Внутри сервера сервисы взаимодействуют через локальный loopback `127.0.0.1`.
  - Код проекта не модифицирован.

### Запущенные службы:
1. **`bondsscreener-db.service`** — микросервис базы данных SQLite (`db_repository`), порт `8964`.
2. **`bondsscreener-backend.service`** — основной API (`backend`) на Gunicorn + Uvicorn workers, порт `8000`.
3. **`bondsscreener-conversion.service`** — сервис загрузки и конвертации данных (`conversion_service`), порт `12345`.
4. **Nginx** — веб-сервер (порт `80`), отдающий статику фронтенда и проксирующий запросы:
   - `/api/` ➔ `http://127.0.0.1:8000/api/`
   - `/conversion-api/` ➔ `http://127.0.0.1:12345/api/`
   - `/` ➔ React/Vite SPA (`frontend/dist`)

---

## Шаг 1. Первичная настройка сервера (выполняется 1 раз)

Подключитесь к вашему Debian-серверу по SSH:

```bash
ssh user@YOUR_SERVER_IP
```

### 1.1. Клонирование репозитория
Рекомендуемый каталог установки — `/opt/bondsscreener`:

```bash
# Даем права на каталог /opt вашему пользователю (например, debian):
sudo mkdir -p /opt/bondsscreener
sudo chown -R $USER:$USER /opt/bondsscreener

# Клонируем проект
git clone https://github.com/ВАШ_ПОЛЬЗОВАТЕЛЬ/BondsScreener.git /opt/bondsscreener
cd /opt/bondsscreener
```

### 1.2. Запуск скрипта автоматической настройки
Запустите скрипт первичной инициализации:

```bash
sudo bash deploy/setup_server.sh
```

**Что скрипт сделает автоматически:**
- Установит все необходимые системные пакеты (Python, Nginx, SQLite3, build-essential, git, rsync и т.д.).
- Создаст виртуальное окружение `.venv` и установит зависимости для всех 3 сервисов.
- Сгенерирует надежные случайные ключи для `.env` (`DB_REPOSITORY_API_KEY`, `AUTH_SECRET_KEY`).
- Создаст и запустит systemd-службы (`bondsscreener-db`, `bondsscreener-backend`, `bondsscreener-conversion`).
- Настроит Nginx на 80 порт и перезапустит его.
- Настроит права `sudo` без пароля для рестарта служб при деплое.

---

## Шаг 2. Настройка секретов в GitHub (для CI/CD)

В вашем репозитории на GitHub перейдите в:
**Settings** ➔ **Secrets and variables** ➔ **Actions** ➔ **New repository secret**.

Добавьте следующие секреты:

| Имя секрета | Значение | Описание |
|---|---|---|
| `SSH_HOST` | `194.xxx.xxx.xxx` | IP-адрес вашего Debian сервера |
| `SSH_USER` | `debian` (или `root`) | Пользователь для SSH подключения |
| `SSH_KEY` | `-----BEGIN OPENSSH PRIVATE KEY...` | Приватный SSH-ключ для авторизации |
| `SSH_PORT` | `22` *(опционально)* | Порт SSH (по умолчанию 22) |
| `DEPLOY_PATH` | `/opt/bondsscreener` *(опционально)* | Путь к каталогу проекта на сервере |

> **Подсказка:** Для генерации выделенного ключа для GitHub Actions:
> ```bash
> ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy -N ""
> cat ~/.ssh/github_deploy.pub >> ~/.ssh/authorized_keys
> ```
> Значение из `~/.ssh/github_deploy` вставьте в секрет `SSH_KEY`.

---

## Шаг 3. Как работает автоматический деплой

При каждом пуше в ветку `main`:
1. GitHub Actions запускает раннер.
2. Собирает фронтенд (`npm run build`) с относительными путями API.
3. Подключается к серверу по SSH.
4. Передает архив фронтенда, обновляет репозиторий через `git pull`.
5. Обновляет зависимости Python при необходимости.
6. Перезапускает службы:
   ```bash
   sudo systemctl restart bondsscreener-db
   sudo systemctl restart bondsscreener-backend
   sudo systemctl restart bondsscreener-conversion
   sudo systemctl reload nginx
   ```
7. Проверяет health check эндпоинт.

Также деплой можно запустить вручную в любой момент из вкладки **Actions** ➔ **Deploy to Debian Server** ➔ **Run workflow**.

---

## Полезные команды для управления на сервере

```bash
# Просмотр статуса всех служб проекта
systemctl status bondsscreener-backend bondsscreener-db bondsscreener-conversion

# Просмотр логов в реальном времени
journalctl -u bondsscreener-backend -f
journalctl -u bondsscreener-db -f
journalctl -u bondsscreener-conversion -f

# Перезапуск сервисов вручную
sudo systemctl restart bondsscreener-backend
sudo systemctl restart bondsscreener-db
sudo systemctl restart bondsscreener-conversion

# Проверка Nginx
sudo nginx -t
sudo systemctl reload nginx
```

