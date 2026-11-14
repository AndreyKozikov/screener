from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import os
import threading
from typing import Optional, List, Any
from urllib.parse import quote
from urllib.request import Request, urlopen
import orjson
import requests

logger = logging.getLogger(__name__)

# Ограничение параллельных запросов к MOEX ISS и шаг логирования прогресса.
_MAX_WORKERS = 16
_PROGRESS_STEP = 200
_BOND_DESCRIPTION_IGNORED_FIELDS = {
    "SECID",
    "NAME",
    "SHORTNAME",
    "ISIN",
    "LISTLEVEL",
    "COUPONFREQUENCY",
    "COUPONDATE",
}


class MoexLoader:

    def __init__(self, url: Optional[str] = None, timeout: int = 30, user_agent: str = "Mozilla/5.0"):
        self.url = url
        self.timeout = timeout
        self.user_agent = user_agent
        self._session_local = threading.local()

    def _get_session(self) -> requests.Session:
        """Возвращает переиспользуемую HTTP-сессию для текущего потока."""
        session = getattr(self._session_local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update({"User-Agent": self.user_agent})
            self._session_local.session = session
        return session

    @staticmethod
    def _worker_count(total: int) -> int:
        if total <= 1:
            return 1
        cpu = os.cpu_count() or 4
        return min(_MAX_WORKERS, max(4, cpu * 2), total)

    def bonds_data_load(self, url):
        request = Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw_payload = response.read()
            # self._logger.info(f"[MOEX] Загружено {len(raw_payload)} байт")
        except Exception as exc:
            # self._logger.error(f"[MOEX] Ошибка загрузки с {url}: {exc}")
            raise RuntimeError(f"Failed to download bonds data: {exc}") from exc

        try:
            payload = orjson.loads(raw_payload)
            # self._logger.info("[MOEX] JSON успешно распарсен")
            return payload
        except orjson.JSONDecodeError as exc:
            # self._logger.error(f"[MOEX] Некорректный JSON: {exc}")
            raise RuntimeError(
                "Received invalid JSON while refreshing bonds data"
            ) from exc

    def _emitent_info_load_one(self, secid: str) -> Optional[dict[str, Any]]:
        """Загружает данные эмитента по одному SECID с MOEX ISS."""
        url = f"https://iss.moex.com/iss/securities.json?q={secid}"
        try:
            response = self._get_session().get(url, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            return None

        securities = payload.get("securities", {})
        columns = securities.get("columns", [])
        data = securities.get("data", [])

        if not data:
            return None

        emitent_info = dict(zip(columns, data[0]))

        try:
            emitent_info["emitent_id"] = int(emitent_info["emitent_id"])
        except (KeyError, ValueError, TypeError):
            return None

        inn = emitent_info.get("emitent_inn")
        if inn is None:
            return None

        inn = str(inn).strip()
        if not inn:
            return None
        emitent_info["emitent_inn"] = inn
        return emitent_info

    def _load_emitent_infos(self, secids: list[str]) -> dict[str, dict[str, Any]]:
        total = len(secids)
        infos: dict[str, dict[str, Any]] = {}
        if total == 0:
            return infos

        workers = self._worker_count(total)
        logger.info(
            "[EMITENTS] Загрузка данных эмитентов с MOEX: %s бумаг, потоков: %s",
            total, workers,
        )

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._emitent_info_load_one, secid): secid
                for secid in secids
            }
            for processed, future in enumerate(as_completed(futures), 1):
                secid = futures[future]
                try:
                    info = future.result()
                except Exception as exc:
                    logger.warning(
                        "[EMITENTS] Ошибка загрузки эмитента по %s: %s", secid, exc,
                    )
                    info = None
                if info is not None:
                    infos[secid] = info
                if processed % _PROGRESS_STEP == 0 or processed == total:
                    unique_emitents = len({item["emitent_inn"] for item in infos.values()})
                    logger.info(
                        "[EMITENTS] Обработано %s/%s бумаг, найдено эмитентов: %s",
                        processed, total, unique_emitents,
                    )

        return infos

    def _load_ratings(
        self, emitent_ids: list[int],
    ) -> dict[int, Optional[list[dict[str, Any]]]]:
        ratings: dict[int, Optional[list[dict[str, Any]]]] = {}
        total = len(emitent_ids)
        if total == 0:
            return ratings

        workers = self._worker_count(total)
        logger.info(
            "[EMITENTS] Загрузка рейтингов эмитентов: %s, потоков: %s",
            total, workers,
        )

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self.emitent_ratings_load, emitent_id): emitent_id
                for emitent_id in emitent_ids
            }
            for processed, future in enumerate(as_completed(futures), 1):
                emitent_id = futures[future]
                try:
                    ratings[emitent_id] = future.result()
                except Exception as exc:
                    logger.warning(
                        "[EMITENTS] Ошибка загрузки рейтингов для MOEX ID %s: %s",
                        emitent_id, exc,
                    )
                    ratings[emitent_id] = None
                if processed % _PROGRESS_STEP == 0 or processed == total:
                    logger.info(
                        "[EMITENTS] Рейтинги: обработано %s/%s",
                        processed, total,
                    )

        return ratings

    def emitent_info_load(self, secids: list[str]):
        infos = self._load_emitent_infos(secids)

        seen_inn: set[str] = set()
        emitents: list[dict[str, Any]] = []
        secid_to_inn: dict[str, str] = {}
        emitent_ids: list[int] = []

        for secid in secids:
            info = infos.get(secid)
            if info is None:
                continue

            inn = info["emitent_inn"]
            secid_to_inn[secid] = inn

            # Эмитента добавляем только один раз
            if inn in seen_inn:
                continue

            seen_inn.add(inn)
            emitents.append(info)
            emitent_ids.append(info["emitent_id"])

        ratings_by_emitent_id = self._load_ratings(emitent_ids)

        inn_to_ratings: dict[str, list[dict[str, Any]]] = {}
        for secid, inn in secid_to_inn.items():
            emitent_id = infos[secid]["emitent_id"]
            inn_to_ratings[inn] = ratings_by_emitent_id.get(emitent_id) or []

        logger.info(
            "[EMITENTS] Данные загружены: бумаг %s, эмитентов %s, связей secid->inn %s",
            len(secids), len(emitents), len(secid_to_inn),
        )

        return {
            "emitents": emitents,
            "inn_to_ratings": inn_to_ratings,
        }

    def bond_descriptions_load(self, secids: list[str]) -> dict[str, dict[str, Any]]:
        """Loads MOEX descriptions for the supplied bonds."""
        return self._load_bond_descriptions(secids)

    def _bond_description_load_one(self, secid: str) -> Optional[dict[str, Any]]:
        """Loads and filters one security's MOEX description block."""
        url = (
            "https://iss.moex.com/iss/securities/"
            f"{quote(secid, safe='')}.json?iss.meta=on&iss.json=extended"
        )
        try:
            response = self._get_session().get(url, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            logger.warning("[BOND_DESCRIPTION] Не удалось загрузить description для %s", secid)
            return None

        entries = self._extract_description_entries(payload)
        if not entries:
            logger.warning("[BOND_DESCRIPTION] В ответе MOEX нет description для %s", secid)
            return None

        result: dict[str, Any] = {}
        for entry in entries:
            name = entry.get("name")
            if not isinstance(name, str) or name in _BOND_DESCRIPTION_IGNORED_FIELDS:
                continue
            if "value" in entry:
                result[name] = entry["value"]
        return result

    @staticmethod
    def _extract_description_entries(payload: Any) -> list[dict[str, Any]]:
        """Supports both ISS extended blocks and the columns/data representation."""
        description = None
        if isinstance(payload, dict):
            description = payload.get("description")
        elif isinstance(payload, list):
            for block in payload:
                if isinstance(block, dict) and "description" in block:
                    description = block["description"]
                    break
        if isinstance(description, dict):
            data = description.get("data", [])
            if data and isinstance(data[0], dict):
                return [row for row in data if isinstance(row, dict)]
            columns = description.get("columns", [])
            if columns and data:
                return [
                    dict(zip(columns, row))
                    for row in data
                    if isinstance(row, (list, tuple)) and len(row) == len(columns)
                ]
            return []

        if isinstance(description, list):
            direct_entries = [
                row for row in description
                if isinstance(row, dict) and "name" in row and "value" in row
            ]
            if direct_entries:
                return direct_entries
            for block in description:
                if isinstance(block, list):
                    rows = [
                        row for row in block
                        if isinstance(row, dict) and "name" in row and "value" in row
                    ]
                    if rows:
                        return rows
        return []

    def _load_bond_descriptions(self, secids: list[str]) -> dict[str, dict[str, Any]]:
        total = len(secids)
        descriptions: dict[str, dict[str, Any]] = {}
        if total == 0:
            return descriptions

        workers = self._worker_count(total)
        logger.info(
            "[BOND_DESCRIPTION] Загрузка description MOEX: %s бумаг, потоков: %s",
            total,
            workers,
        )
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._bond_description_load_one, secid): secid
                for secid in secids
            }
            for processed, future in enumerate(as_completed(futures), 1):
                secid = futures[future]
                try:
                    data = future.result()
                except Exception as exc:
                    logger.warning(
                        "[BOND_DESCRIPTION] Ошибка загрузки description для %s: %s",
                        secid,
                        exc,
                    )
                    data = None
                if data is not None:
                    descriptions[secid] = data
                if processed % _PROGRESS_STEP == 0 or processed == total:
                    logger.info(
                        "[BOND_DESCRIPTION] Обработано %s/%s бумаг",
                        processed,
                        total,
                    )
        return descriptions

    def emitent_ratings_load(self, emitent_id: int) -> Optional[list[dict[str, Any]]]:
        url = f"https://iss.moex.com/iss/cci/rating/companies/ecbd_{emitent_id}.json?iss.json=extended&iss.meta=off"
        try:
            response = self._get_session().get(url, timeout=self.timeout)
            response.raise_for_status()
            json_data = response.json()

            if not isinstance(json_data, list) or len(json_data) < 2:
                return None
            return json_data[1]["cci_rating_companies"]

        except requests.RequestException:
            return None

        except (KeyError, TypeError, ValueError):
            return None


moex_loader: Optional[MoexLoader] = None


def get_moex_loader():
    global moex_loader
    if moex_loader is None:
        moex_loader = MoexLoader()
    return moex_loader
