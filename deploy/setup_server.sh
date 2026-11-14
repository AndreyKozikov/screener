#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Скрипт первичной настройки сервера Debian для BondsScreener (Bare-metal)
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEPLOY_USER="${1:-${SUDO_USER:-deploy}}"

echo "=== [1/7] Проверка окружения ==="
echo "Каталог проекта: ${APP_DIR}"
echo "Пользователь:    ${DEPLOY_USER}"

# Проверка прав sudo/root
if [ "$(id -u)" -ne 0 ]; then
    echo "Ошибка: запустите скрипт с правами sudo: sudo bash deploy/setup_server.sh" >&2
    exit 1
fi

echo "=== [2/7] Установка системных зависимостей Debian ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    python3-dev \
    build-essential \
    nginx \
    redis-server \
    git \
    curl \
    rsync \
    tar \
    sqlite3 \
    libsqlite3-dev

systemctl enable --now redis-server

echo "=== [3/7] Создание необходимых каталогов данных ==="
mkdir -p "${APP_DIR}/db_repository/data/db"
mkdir -p "${APP_DIR}/backend/app/data/events"
mkdir -p "${APP_DIR}/backend/logs"
mkdir -p "${APP_DIR}/frontend/dist"

# Временная страница-заглушка для Nginx, пока не собран фронтенд
if [ ! -f "${APP_DIR}/frontend/dist/index.html" ]; then
    echo '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Bonds Screener</title></head><body><h1>Bonds Screener запущен. Ожидание сборки фронтенда...</h1></body></html>' > "${APP_DIR}/frontend/dist/index.html"
fi

chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "${APP_DIR}"

echo "=== [4/7] Настройка Python окружения (.venv) ==="
if [ ! -d "${APP_DIR}/.venv" ]; then
    echo "Создание виртуального окружения..."
    sudo -u "${DEPLOY_USER}" python3 -m venv "${APP_DIR}/.venv"
fi

echo "Обновление pip и установка зависимостей..."
sudo -u "${DEPLOY_USER}" "${APP_DIR}/.venv/bin/pip" install --upgrade pip
sudo -u "${DEPLOY_USER}" "${APP_DIR}/.venv/bin/pip" install gunicorn

if [ -f "${APP_DIR}/backend/requirements.txt" ]; then
    echo "Установка зависимостей backend..."
    sudo -u "${DEPLOY_USER}" "${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/backend/requirements.txt"
fi

if [ -f "${APP_DIR}/db_repository/requirements.txt" ]; then
    echo "Установка зависимостей db_repository..."
    sudo -u "${DEPLOY_USER}" "${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/db_repository/requirements.txt"
fi

if [ -f "${APP_DIR}/conversion_service/requirements.txt" ]; then
    echo "Установка зависимостей conversion_service..."
    sudo -u "${DEPLOY_USER}" "${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/conversion_service/requirements.txt"
fi

echo "=== [5/7] Инициализация конфигураций и ключей безопасности ==="
# Генерация ключей для .env при их отсутствии
GEN_DB_KEY=$(openssl rand -hex 24)
GEN_AUTH_KEY=$(openssl rand -hex 32)

# db_repository
if [ ! -f "${APP_DIR}/db_repository/config/config.toml" ] && [ -f "${APP_DIR}/db_repository/config/config.example.toml" ]; then
    cp "${APP_DIR}/db_repository/config/config.example.toml" "${APP_DIR}/db_repository/config/config.toml"
fi
if [ ! -f "${APP_DIR}/db_repository/.env" ]; then
    cat <<EOF > "${APP_DIR}/db_repository/.env"
DB_REPOSITORY_API_KEY=${GEN_DB_KEY}
EOF
fi

# backend
if [ ! -f "${APP_DIR}/backend/config/config.toml" ] && [ -f "${APP_DIR}/backend/config/config.example.toml" ]; then
    cp "${APP_DIR}/backend/config/config.example.toml" "${APP_DIR}/backend/config/config.toml"
fi
if [ ! -f "${APP_DIR}/backend/.env" ]; then
    cat <<EOF > "${APP_DIR}/backend/.env"
DB_REPOSITORY_API_KEY=${GEN_DB_KEY}
AUTH_SECRET_KEY=${GEN_AUTH_KEY}
EOF
fi
if ! grep -q '^AGENT_REDIS_URL=' "${APP_DIR}/backend/.env"; then
    printf '\nAGENT_REDIS_URL=redis://127.0.0.1:6379/1\n' >> "${APP_DIR}/backend/.env"
fi

# conversion_service
if [ ! -f "${APP_DIR}/conversion_service/config/config.toml" ] && [ -f "${APP_DIR}/conversion_service/config/config.example.toml" ]; then
    cp "${APP_DIR}/conversion_service/config/config.example.toml" "${APP_DIR}/conversion_service/config/config.toml"
fi
if [ ! -f "${APP_DIR}/conversion_service/.env" ]; then
    cat <<EOF > "${APP_DIR}/conversion_service/.env"
DB_REPOSITORY_API_KEY=${GEN_DB_KEY}
AUTH_SECRET_KEY=${GEN_AUTH_KEY}
EOF
fi

chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "${APP_DIR}"

echo "=== [6/7] Установка Systemd служб и прав sudo ==="
# Настройка sudo без пароля для перезапуска служб (нужно для GitHub Actions CI/CD)
SUDOERS_FILE="/etc/sudoers.d/bondsscreener"
cat <<EOF > "${SUDOERS_FILE}"
${DEPLOY_USER} ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart bondsscreener-*, /usr/bin/systemctl reload nginx, /usr/bin/systemctl status bondsscreener-*, /usr/bin/systemctl start bondsscreener-*, /usr/bin/systemctl stop bondsscreener-*
EOF
chmod 0440 "${SUDOERS_FILE}"

# Установка служб
for svc in bondsscreener-db bondsscreener-backend bondsscreener-conversion; do
    sed -e "s|{{APP_DIR}}|${APP_DIR}|g" \
        -e "s|{{DEPLOY_USER}}|${DEPLOY_USER}|g" \
        "${SCRIPT_DIR}/systemd/${svc}.service" > "/etc/systemd/system/${svc}.service"
    chmod 644 "/etc/systemd/system/${svc}.service"
done

systemctl daemon-reload
systemctl enable bondsscreener-db bondsscreener-backend bondsscreener-conversion

echo "=== [7/7] Настройка Nginx ==="
sed "s|{{APP_DIR}}|${APP_DIR}|g" "${SCRIPT_DIR}/nginx/bondsscreener.conf" > /etc/nginx/sites-available/bondsscreener.conf
ln -sf /etc/nginx/sites-available/bondsscreener.conf /etc/nginx/sites-enabled/bondsscreener.conf

# Отключаем default-хост nginx, чтобы наш сайт отвечал по IP на 80 порту
if [ -f /etc/nginx/sites-enabled/default ]; then
    rm -f /etc/nginx/sites-enabled/default
fi

nginx -t
systemctl restart nginx

echo "Запуск сервисов проекта..."
systemctl restart bondsscreener-db
sleep 2
systemctl restart bondsscreener-backend
systemctl restart bondsscreener-conversion

echo "=== Первичная настройка успешно завершена! ==="
echo "Статус служб:"
systemctl status bondsscreener-db --no-pager -n 3 || true
systemctl status bondsscreener-backend --no-pager -n 3 || true
systemctl status bondsscreener-conversion --no-pager -n 3 || true

