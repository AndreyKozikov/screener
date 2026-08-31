import asyncio
from typing import Optional
from conversion_service.app.utils.moex_loader import MoexLoader

import httpx


class Emitents:

    def __init__(self):
        self.moex_loader = MoexLoader()

    async def update_emitents_data(self, secids: Optional[list[str]]):
        reset = False
        if secids is None:
            try:
                async with httpx.AsyncClient(timeout=600) as client:
                    response = await client.get(
                        url="http://127.0.0.1:8964/api/all_secids",
                        headers={"Content-Type": "application/json"},
                    )
                    response.raise_for_status()
                    secids = response.json()
                    reset = True
            except Exception as e:
                raise
        data = await asyncio.to_thread(
            self.moex_loader.emitent_info_load,
            secids
        )
        data["reset"] = reset
        try:
            async with httpx.AsyncClient(timeout=600) as client:
                response = await client.post(
                    url="http://127.0.0.1:8964/api/emitents/update",
                    json=data,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                result = response.json()
        except Exception as e:
            raise
        return result


emitent_service: Optional[Emitents] = None

def get_emitent_service():
    global emitent_service
    if emitent_service is None:
        emitent_service = Emitents()
    return emitent_service