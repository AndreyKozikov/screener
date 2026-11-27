#!/usr/bin/env bash
set -euo pipefail

# Установка корневого и двух промежуточных сертификатов Russian Trusted CA
# на Debian/Ubuntu. Требуется для TLS-проверки сервисов MOEX, использующих
# цепочку российского национального УЦ.

if [[ $EUID -ne 0 ]]; then
  echo "Ошибка: запустите скрипт через sudo: sudo $0" >&2
  exit 1
fi

apt-get update
apt-get install -y ca-certificates curl openssl

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT
cd "$work_dir"

download() {
  local url="$1"
  local file="$2"
  echo "Скачивание: $file"
  curl -fL --retry 3 --retry-delay 2 -o "$file" "$url"
}

download https://gu-st.ru/content/downloads/Russian_Trusted_Root_CA.cer Russian_Trusted_Root_CA.cer
download https://gu-st.ru/content/downloads/Russian_Trusted_Sub_CA.cer Russian_Trusted_Sub_CA.cer
download https://gu-st.ru/content/downloads/Russian_Trusted_Sub_CA_2024.cer Russian_Trusted_Sub_CA_2024.cer

check_certificate() {
  local cert="$1"

  echo "Проверка сертификата: $cert"

  if openssl x509 -in "$cert" -noout -subject -issuer -dates >/dev/null 2>&1; then
    openssl x509 -in "$cert" -noout -subject -issuer -dates
    return 0
  fi

  if openssl x509 -inform DER -in "$cert" -noout -subject -issuer -dates >/dev/null 2>&1; then
    openssl x509 -inform DER -in "$cert" -noout -subject -issuer -dates
    return 0
  fi

  echo "Ошибка: не удалось распознать сертификат $cert как PEM или DER." >&2
  exit 1
}

for cert in \
  Russian_Trusted_Root_CA.cer \
  Russian_Trusted_Sub_CA.cer \
  Russian_Trusted_Sub_CA_2024.cer
do
  check_certificate "$cert"
done

install -m 0644 Russian_Trusted_Root_CA.cer \
  /usr/local/share/ca-certificates/Russian_Trusted_Root_CA.crt

install -m 0644 Russian_Trusted_Sub_CA.cer \
  /usr/local/share/ca-certificates/Russian_Trusted_Sub_CA.crt

install -m 0644 Russian_Trusted_Sub_CA_2024.cer \
  /usr/local/share/ca-certificates/Russian_Trusted_Sub_CA_2024.crt

update-ca-certificates

echo
echo "Проверка TLS-цепочки MOEX..."
if openssl s_client -connect iss.moex.com:443 -servername iss.moex.com </dev/null 2>&1 \
  | grep -q "Verify return code: 0 (ok)"
then
  echo "OK: сертификат MOEX успешно проверен."
else
  echo "ВНИМАНИЕ: проверка сертификата MOEX не прошла. Покажите вывод:" >&2
  echo "openssl s_client -connect iss.moex.com:443 -servername iss.moex.com -showcerts </dev/null" >&2
  exit 1
fi

echo
echo "Проверка HTTPS-запроса из Python..."
python3 - <<'PY'
import urllib.request

url = "https://iss.moex.com/iss/engines/stock/markets/bonds/boards/TQOB/securities.json"
with urllib.request.urlopen(url, timeout=15) as response:
    print(f"OK: HTTP {response.status}")
PY

echo
echo "Готово. Сертификаты НУЦ установлены. Перезапустите conversion_service вручную."
