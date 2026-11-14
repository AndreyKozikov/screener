#!/usr/bin/env bash
set -euo pipefail

# One-time manual Redis setup for the Debian BondsScreener server.
# Run after connecting over SSH: sudo bash deploy/setup_redis.sh

if [[ "${EUID}" -ne 0 ]]; then
    echo "Запустите скрипт с правами root: sudo bash deploy/setup_redis.sh" >&2
    exit 1
fi

if [[ ! -r /etc/os-release ]] || ! grep -qE '^ID=(debian|ubuntu)$' /etc/os-release; then
    echo "Скрипт предназначен для Debian/Ubuntu." >&2
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y redis-server

systemctl enable --now redis-server

if ! redis-cli -h 127.0.0.1 -p 6379 ping | grep -qx PONG; then
    echo "Redis установлен, но проверка подключения не прошла." >&2
    systemctl --no-pager --full status redis-server || true
    exit 1
fi

echo "Redis установлен и запущен. Локальная проверка: PONG."
echo "BondsScreener использует redis://127.0.0.1:6379/1 по умолчанию."
