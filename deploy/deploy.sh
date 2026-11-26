#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Скрипт обновления проекта (Deploy) на Debian без использования Docker
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEPLOY_USER="$(id -un)"

echo "=== [1/5] Переход в каталог проекта: ${APP_DIR} ==="
cd "${APP_DIR}"

echo "=== [2/6] Приостановка расписания обновления данных ==="
UPDATE_TIMERS=(
    bondsscreener-data-update-bonds.timer
    bondsscreener-data-update-trading-history.timer
    bondsscreener-data-update-currency.timer
    bondsscreener-data-update-keyrate.timer
    bondsscreener-data-update-zerocupon.timer
    bondsscreener-data-update-ruonia.timer
    bondsscreener-data-update-inflation-expectations.timer
)
UPDATE_TASKS=(bonds trading_history currency keyrate zerocupon ruonia inflation_expectations)
RENDERED_UNITS=()
cleanup_rendered_units() {
    for rendered in "${RENDERED_UNITS[@]}"; do
        rm -f "${rendered}"
    done
}
restart_update_timers() {
    for timer in "${UPDATE_TIMERS[@]}"; do
        sudo systemctl enable "${timer}" >/dev/null 2>&1 || true
        sudo systemctl start "${timer}" >/dev/null 2>&1 || true
    done
    cleanup_rendered_units
}
trap restart_update_timers EXIT
# Stop timers first to prevent new runs, then stop any active oneshot task.
for timer in "${UPDATE_TIMERS[@]}"; do
    sudo systemctl stop "${timer}" 2>/dev/null || true
done
for task in "${UPDATE_TASKS[@]}"; do
    sudo systemctl stop "bondsscreener-data-update@${task}.service" 2>/dev/null || true
done

echo "=== [3/6] Получение свежего кода из Git ==="
BRANCH="${DEPLOY_BRANCH:-main}"
git fetch origin "${BRANCH}"
git reset --hard "origin/${BRANCH}"

echo "=== [4/6] Обновление зависимостей Python ==="
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

echo "=== [5/6] Развертывание фронтенда ==="
publish_frontend() {
    local release_dir="$1"
    local live_dir="${APP_DIR}/frontend/dist"

    mkdir -p "${live_dir}/assets"
    # Hashed assets are immutable and safe to keep from prior releases. Copy
    # them first, then publish index.html last so it never references missing files.
    if [ -d "${release_dir}/assets" ]; then
        cp -a "${release_dir}/assets/." "${live_dir}/assets/"
    fi
    install -m 0644 "${release_dir}/index.html" "${live_dir}/.index.html.new"
    mv -f "${live_dir}/.index.html.new" "${live_dir}/index.html"
}

if [ -f "${APP_DIR}/dist.tar.gz" ]; then
    echo "Распаковка собранного в GitHub Actions фронтенда..."
    RELEASE_TMP="$(mktemp -d "${APP_DIR}/.frontend-release.XXXXXX")"
    tar -xzf "${APP_DIR}/dist.tar.gz" -C "${RELEASE_TMP}"
    publish_frontend "${RELEASE_TMP}/dist"
    rm -rf "${RELEASE_TMP}"
    rm -f "${APP_DIR}/dist.tar.gz"
elif command -v npm >/dev/null 2>&1; then
    echo "Сборка фронтенда на сервере..."
    cd "${APP_DIR}/frontend"
    npm ci
    rm -rf .dist-release
    VITE_API_BASE_URL="/api" npm run build -- --outDir .dist-release
    publish_frontend "${APP_DIR}/frontend/.dist-release"
    rm -rf .dist-release
    cd "${APP_DIR}"
fi

echo "=== [6/6] Установка расписания и перезапуск системных служб ==="
UPDATE_UNIT_FILES=(
    bondsscreener-data-update@.service
    bondsscreener-data-update-bonds.timer
    bondsscreener-data-update-trading-history.timer
    bondsscreener-data-update-currency.timer
    bondsscreener-data-update-keyrate.timer
    bondsscreener-data-update-zerocupon.timer
    bondsscreener-data-update-ruonia.timer
    bondsscreener-data-update-inflation-expectations.timer
)
for unit in "${UPDATE_UNIT_FILES[@]}"; do
    unit_source="${APP_DIR}/deploy/systemd/${unit}"
    if [ ! -f "${unit_source}" ]; then
        echo "Ошибка: не найден systemd unit: ${unit_source}" >&2
        exit 1
    fi
    rendered="${APP_DIR}/deploy/systemd/${unit}.rendered.$$"
    RENDERED_UNITS+=("${rendered}")
    sed -e "s|{{APP_DIR}}|${APP_DIR}|g" \
        -e "s|{{DEPLOY_USER}}|${DEPLOY_USER}|g" \
        "${unit_source}" > "${rendered}"
    sudo install -m 0644 "${rendered}" "/etc/systemd/system/${unit}"
    rm -f "${rendered}"
done
sudo systemctl daemon-reload
sudo systemctl restart bondsscreener-db
sleep 2
sudo systemctl restart bondsscreener-backend
sudo systemctl restart bondsscreener-conversion
sudo systemctl reload nginx

# Starting timers activates only the schedules; it does not start the oneshot jobs.
for timer in "${UPDATE_TIMERS[@]}"; do
    sudo systemctl enable "${timer}"
    sudo systemctl start "${timer}"
done
trap - EXIT

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

