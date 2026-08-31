from pathlib import Path
from typing import Any, Dict, List, Tuple
from datetime import datetime, date

import orjson

BONDS_TYPE_MAPPING_JSON: str = "bonds_type_mapping.json"
BONDS_TYPE43_MAPPING_JSON: str = "bonds_type43_mapping.json"

class BondTransformer:


    def __init__(self):
        pass


    def transform_raw_payload(self, payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:

        data = payload

        securities = data.get("securities", {})
        sec_columns = securities.get("columns", [])
        sec_data = securities.get("data", [])

        marketdata = data.get("marketdata", {})
        md_columns = marketdata.get("columns", [])
        md_data = marketdata.get("data", [])

        yields_section = data.get("marketdata_yields", {})
        yields_columns = yields_section.get("columns", [])
        yields_data = yields_section.get("data", [])
        bonds_data: Dict[str, Dict[str, Any]] = {}

        securities_map = {}

        for row in sec_data:
            record = dict(zip(sec_columns, row))

            secid = record.get("SECID")
            boardid = record.get("BOARDID")
            matdate = record.get("MATDATE")

            if boardid and str(boardid).strip().upper() == "SPOB":
                continue
            if matdate and matdate!="0000-00-00":
                matdate_dt = datetime.strptime(matdate, "%Y-%m-%d").date()
                if matdate_dt <= date.today():
                    continue

            if "BONDTYPE" in record:
                bondtype43_value = record.get("BONDTYPE")
                if bondtype43_value:
                    record["BONDTYPE43"] = (
                        bondtype43_value.strip()
                        if isinstance(bondtype43_value, str)
                        else bondtype43_value
                    )

            if secid and boardid:
                securities_map[(secid, boardid)] = record

        marketdata_map = {}

        for row in md_data:
            record = dict(zip(md_columns, row))

            secid = record.get("SECID")
            boardid = record.get("BOARDID")

            if secid and boardid:
                marketdata_map[(secid, boardid)] = record

        yields_map = {}

        for row in yields_data:
            record = dict(zip(yields_columns, row))

            secid = record.get("SECID")
            boardid = record.get("BOARDID")

            if secid and boardid:
                yields_map[(secid, boardid)] = record

        for key, securities in securities_map.items():
            secid, boardid = key

            bonds_data[secid] = {
                "securities": securities,
                "marketdata": marketdata_map[key],
                "marketdata_yields": yields_map.get(key, {}),
            }

        return bonds_data

    def _read_json(self, path: Path) -> Any:
        """Читает JSON из файла по указанному пути.

        Args:
            path: Путь к JSON файлу.

        Returns:
            Распарсенное значение (dict, list и т.д.).

        Raises:
            OSError: Если не удалось прочитать файл.
            orjson.JSONDecodeError: Если содержимое не является валидным JSON.
        """
        with open(path, "rb") as f:
            return orjson.loads(f.read())

    def load_mappings(self) -> Tuple[Dict[str, int], Dict[str, int]]:

        type_mapping: Dict[str, int] = {}
        kind_mapping: Dict[str, int] = {}
        data_dir = Path(__file__).resolve().parent.parent.parent

        type_path = data_dir / "config" / BONDS_TYPE_MAPPING_JSON

        if type_path.exists():
            try:
                data = self._read_json(type_path)
                if isinstance(data, dict):
                    type_mapping = {k: int(v) for k, v in data.items() if v is not None}
            except Exception as e:
                print(f"Ошибка чтения: {BONDS_TYPE_MAPPING_JSON}")

        kind_path = data_dir / "config" / BONDS_TYPE43_MAPPING_JSON

        if kind_path.exists():
            try:
                data = self._read_json(kind_path)

                if isinstance(data, dict):
                    kind_mapping = {k: int(v) for k, v in data.items() if v is not None}
            except Exception as e:
                print(f"Ошибка чтения: {BONDS_TYPE43_MAPPING_JSON}")

        return type_mapping, kind_mapping