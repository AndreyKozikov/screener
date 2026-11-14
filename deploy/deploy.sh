#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Скрипт обновления проекта (Deploy) на Debian без использования Docker
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== [1/5] Переход в каталог проекта: ${APP_DIR} ==="
cd "${APP_DIR}"

echo "=== [2/5] Получение свежего кода из Git ==="
BRANCH="${DEPLOY_BRANCH:-main}"
git fetch origin "${BRANCH}"
git reset --hard "origin/${BRANCH}"

echo "=== [3/5] Обновление зависимостей Python ==="
if [ -d "${APP_DIR}/.venv" ]; then
    "${APP_DIR}/.venv/bin/pip" install --upgrade pip
    "${APP_DIR}/.venv/bin/pip" install gunicorn
    [ -f "backend/requirements.txt" ] && "${APP_DIR}/.venv/bin/pip" install -r backend/requirements.txt
    [ -f "db_repository/requirements.txt" ] && "${APP_DIR}/.venv/bin/pip" install -r db_repository/requirements.txt
    [ -f "conversion_service/requirements.txt" ] && "${APP_DIR}/.venv/bin/pip" install -r conversion_service/requirements.txt
else
    echo "Внимание: .venv не найден! Запустите deploy/setup_server.sh перед первым деплоем." >&2
    exit 1
fi

echo "=== [4/5] Развертывание фронтенда ==="
if [ -f "${APP_DIR}/dist.tar.gz" ]; then
    echo "Распаковка собранного в GitHub Actions фронтенда..."
    mkdir -p "${APP_DIR}/frontend/dist"
    tar -xzf "${APP_DIR}/dist.tar.gz" -C "${APP_DIR}/frontend"
    rm -f "${APP_DIR}/dist.tar.gz"
elif command -v npm >/dev/null 2>&1; then
    echo "Сборка фронтенда на сервере..."
    cd "${APP_DIR}/frontend"
    npm ci
    VITE_API_BASE_URL="/api" VITE_CONVERSION_API_BASE_URL="/conversion-api" npm run build
    cd "${APP_DIR}"
fi

echo "=== [5/5] Перезапуск системных служб ==="
sudo systemctl restart bondsscreener-db
sleep 2
sudo systemctl restart bondsscreener-backend
sudo systemctl restart bondsscreener-conversion
sudo systemctl reload nginx

echo "Проверка доступности Backend API..."
for i in {1..15}; do
    if curl -s -f http://127.0.0.1:8000/health >/dev/null 2>&1; then
        echo "Сервисы успешно запущены и отвечают!"
        exit 0
    fi
    echo "Ожидание запуска API (попытка $i/15)..."
    sleep 2
done

echo "Предупреждение: health check не ответил за 30 секунд. Проверьте: journalctl -u bondsscreener-backend -n 50"

