from typing import Optional, Any
from db_repository.repository.emitent_repository import get_emitent_repository
from db_repository.repository.ratings_repository import get_ratings_repository


class EmitentService:
    def __init__(self):
        self.emitent_repository = get_emitent_repository()
        self.ratings_repository = get_ratings_repository()

    async def emitents_data_update(self, data: dict[str, Any]):

        if data["reset"]:
            self.emitent_repository.delete_emitents()
            print("Данные об эмитентах удалены")

        secid_to_inn = data["secid_to_inn"]
        inn_to_ratings = data["inn_to_ratings"]
        inns = {item["emitent_inn"] for item in data["emitents"]}
        emitents = [
            {
                "moex_id": item["emitent_id"],
                "inn": item["emitent_inn"],
                "okpo": item["emitent_okpo"],
                "title": item["emitent_title"],
                "type": item["type"],
            }
            for item in data["emitents"]
        ]
        result = self.emitent_repository.update_emitents(emitents)
        
        data = self.emitent_repository.get_emitents_ids(inns)
        inn_to_id = {
            inn: emitent_id
            for inn, emitent_id in data
        }

        secid_to_emitent_id = [
            {
                "secid": secid,
                "emitent_id": inn_to_id[inn],
            }
            for secid, inn in secid_to_inn.items()
        ]

        result = self.emitent_repository.update_emitent_ids_to_bond(secid_to_emitent_id)

        emitent_id_to_ratings = [
            {
                "emitent_id": inn_to_id[inn],
                "agency_id": rating["agency_id"],
                "rating_level_name": rating["rating_level_name_short_ru"],
                "rating_date": rating["rating_date"],
                "rating_publicate_date": rating["rating_publicate_date"],
            }
            for inn, ratings in inn_to_ratings.items()
            for rating in ratings
        ]
        self.ratings_repository.update_emitents_rating(emitent_id_to_ratings)

        return result


emitent_service: Optional[EmitentService] = None


def get_emitent_service():
    global emitent_service
    if emitent_service is None:
        emitent_service = EmitentService()
    return emitent_service
