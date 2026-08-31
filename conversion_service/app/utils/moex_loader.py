from typing import Optional, List, Any
from urllib.request import Request, urlopen
import orjson
import requests


class MoexLoader:

    def __init__(self, url: Optional[str] = None, timeout: int = 30, user_agent: str = "Mozilla/5.0"):
        self.url = url
        self.timeout = timeout
        self.user_agent = user_agent

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

    def emitent_info_load(self, secids: list[str]):
        emitents: list[dict[str, Any]] = []
        secid_to_inn: dict[str, str] = {}
        inn_to_ratings: dict[str, list[dict[str, Any]]] = {}

        seen_inn: set[str] = set()
        ratings_cache: dict[int, Optional[list[dict[str, Any]]]] = {}

        for secid in secids:
            url = f"https://iss.moex.com/iss/securities.json?q={secid}"
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            try:
                with urlopen(request, timeout=30) as response:
                    raw_payload = response.read()
            except Exception as e:
                continue

            try:
                payload = orjson.loads(raw_payload)
            except orjson.JSONDecodeError as e:
                continue

            securities = payload.get("securities", {})
            columns = securities.get("columns", [])
            data = securities.get("data", [])

            if not data:
                continue

            emitent_info = dict(zip(columns, data[0]))

            try:
                emitent_id = int(emitent_info["emitent_id"])
            except (KeyError, ValueError, TypeError):
                continue

            inn = emitent_info.get("emitent_inn")
            if inn is None:
                continue

            inn = str(inn).strip()
            secid_to_inn[secid] = inn

            if emitent_id not in ratings_cache:
                ratings_cache[emitent_id] = self.emitent_ratings_load(emitent_id)

            ratings = ratings_cache[emitent_id]

            inn_to_ratings[inn] = ratings or []

            # Эмитента добавляем только один раз
            if inn in seen_inn:
                continue

            seen_inn.add(inn)

            emitents.append(emitent_info)

        return {
            "emitents": emitents,
            "secid_to_inn": secid_to_inn,
            "inn_to_ratings": inn_to_ratings,
        }

    def emitent_ratings_load(self, emitent_id: int) -> Optional[list[dict[str, Any]]]:
        url = f"https://iss.moex.com/iss/cci/rating/companies/ecbd_{emitent_id}.json?iss.json=extended&iss.meta=off"
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=30,
            )
            response.raise_for_status()
            json_data = response.json()

            if not isinstance(json_data, list) or len(json_data) < 2:
                return None
            return json_data[1]["cci_rating_companies"]

        except requests.RequestException as exc:
            return None

        except (KeyError, TypeError):
            return None


moex_loader: Optional[MoexLoader] = None


def get_moex_loader():
    global moex_loader
    if moex_loader is None:
        moex_loader = MoexLoader()
    return moex_loader
