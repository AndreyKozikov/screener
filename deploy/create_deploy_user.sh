#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Скрипт создания выделенного пользователя для деплоя на Debian
# Запуск от root (или с sudo): sudo bash deploy/create_deploy_user.sh
# ==============================================================================

DEPLOY_USER="deploy"
APP_DIR="/opt/bondsscreener"

if [ "$(id -u)" -ne 0 ]; then
    echo "Ошибка: запустите скрипт с правами root или sudo: sudo bash deploy/create_deploy_user.sh" >&2
    exit 1
fi

echo "=== [1/5] Создание пользователя ${DEPLOY_USER} ==="
if id "${DEPLOY_USER}" >/dev/null 2>&1; then
    echo "Пользователь ${DEPLOY_USER} уже существует."
else
    # Создаем системного пользователя с домашним каталогом и bash
    adduser --disabled-password --gecos "BondsScreener Deploy User" "${DEPLOY_USER}"
    echo "Пользователь ${DEPLOY_USER} успешно создан."
fi

# Добавляем в группу systemd-journal (чтобы читать логи journalctl без sudo)
usermod -aG systemd-journal "${DEPLOY_USER}"

echo "=== [2/5] Настройка SSH для ${DEPLOY_USER} ==="
SSH_DIR="/home/${DEPLOY_USER}/.ssh"
mkdir -p "${SSH_DIR}"
chmod 700 "${SSH_DIR}"
touch "${SSH_DIR}/authorized_keys"
chmod 600 "${SSH_DIR}/authorized_keys"

# Генерируем выделенную пару SSH-ключей для GitHub Actions, если её еще нет
KEY_PATH="${SSH_DIR}/github_actions"
if [ ! -f "${KEY_PATH}" ]; then
    ssh-keygen -t ed25519 -C "github-actions-bondsscreener" -f "${KEY_PATH}" -N ""
    cat "${KEY_PATH}.pub" >> "${SSH_DIR}/authorized_keys"
    echo "Новая SSH пара ключей сгенерирована."
fi

chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "${SSH_DIR}"

echo "=== [3/5] Настройка ограниченных прав sudo без пароля ==="
SUDOERS_FILE="/etc/sudoers.d/bondsscreener-deploy"
cat <<EOF > "${SUDOERS_FILE}"
# Разрешаем пользователю deploy перезапускать только нужные службы и проверять nginx
${DEPLOY_USER} ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart bondsscreener-*, /usr/bin/systemctl reload nginx, /usr/bin/systemctl status bondsscreener-*, /usr/bin/systemctl start bondsscreener-*, /usr/bin/systemctl stop bondsscreener-*, /usr/sbin/nginx -t
EOF
chmod 0440 "${SUDOERS_FILE}"

echo "=== [4/5] Подготовка рабочего каталога ${APP_DIR} ==="
mkdir -p "${APP_DIR}"
chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "${APP_DIR}"
chmod 755 "${APP_DIR}"

echo "=== [5/5] Готово! Данные для GitHub Secrets: ==="
echo ""
echo "------------------- [СКОПИРУЙТЕ ЭТОТ ПРИВАТНЫЙ КЛЮЧ] -------------------"
echo "Добавьте этот текст в GitHub Secrets под именем SSH_KEY:"
echo ""
cat "${KEY_PATH}"
echo ""
echo "------------------------------------------------------------------------"
echo "SSH_USER: ${DEPLOY_USER}"
echo "DEPLOY_PATH: ${APP_DIR}"
echo ""
echo "Теперь вы можете подключиться из GitHub Actions или вручную от имени ${DEPLOY_USER}."

