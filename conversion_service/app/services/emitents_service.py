import asyncio
import logging
from typing import Optional
from conversion_service.app.utils.moex_loader import MoexLoader

import httpx

logger = logging.getLogger(__name__)


class Emitents:

    def __init__(self):
        self.moex_loader = MoexLoader()

    async def update_emitents_data(self, secids: Optional[list[str]]):
        reset = False
        if secids is None:
            logger.info("[EMITENTS] Запрос списка SECID из db_repository")
            try:
                async with httpx.AsyncClient(timeout=600) as client:
                    response = await client.get(
                        url="http://127.0.0.1:8964/api/all_secids",
                        headers={"Content-Type": "application/json"},
                    )
                    response.raise_for_status()
                    secids = response.json()
                    reset = True
            except Exception:
                logger.exception("[EMITENTS] Не удалось получить список SECID из db_repository")
                raise
            logger.info("[EMITENTS] Получено SECID: %s", len(secids))
        else:
            logger.info("[EMITENTS] Обновление для переданных SECID: %s", len(secids))

        logger.info("[EMITENTS] Старт загрузки эмитентов с MOEX (может занять несколько минут)")
        data = await asyncio.to_thread(
            self.moex_loader.emitent_info_load,
            secids
        )
        logger.info(
            "[EMITENTS] С MOEX загружено эмитентов: %s, связей secid->inn: %s",
            len(data["emitents"]), len(data["secid_to_inn"]),
        )
        data["reset"] = reset

        logger.info("[EMITENTS] Сохранение данных в db_repository")
        try:
            async with httpx.AsyncClient(timeout=600) as client:
                response = await client.post(
                    url="http://127.0.0.1:8964/api/emitents/update",
                    json=data,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                result = response.json()
        except Exception:
            logger.exception("[EMITENTS] Не удалось сохранить эмитентов в db_repository")
            raise
        logger.info("[EMITENTS] Обновление эмитентов завершено")
        return result


emitent_service: Optional[Emitents] = None

def get_emitent_service():
    global emitent_service
    if emitent_service is None:
        emitent_service = Emitents()
    return emitent_service