"""Загрузчик данных о купонах облигаций из кэша.

Этот модуль содержит класс CouponLoader для загрузки и кэширования данных о купонах
из файла coupons_data.json. Предоставляет метод для получения значения ближайшего
купона для облигации.
"""

from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

import orjson


class CouponLoader:
    """Вспомогательный сервис для загрузки данных о купонах из coupons_data.json.
    
    Класс обеспечивает загрузку данных о купонах облигаций из JSON файла с кэшированием
    для повышения производительности. Предоставляет метод для получения значения
    ближайшего купона для облигации.
    
    Attributes:
        data_dir: Путь к директории с данными.
        coupons_file: Путь к файлу coupons_data.json.
        _coupons_cache: Кэш загруженных данных о купонах.
    """
    
    def __init__(self, data_dir: Path):
        """Инициализирует загрузчик купонов.
        
        Args:
            data_dir: Путь к директории с JSON файлами данных.
        """
        from config.paths import COUPONS_DATA_JSON
        self.data_dir = data_dir
        self.coupons_file = data_dir / COUPONS_DATA_JSON
        self._coupons_cache: Optional[Dict[str, Dict]] = None
    
    def _load_coupons_data(self) -> Dict[str, Dict]:
        """Загружает данные о купонах из JSON файла.
        
        Загружает данные из файла coupons_data.json с кэшированием. При первом вызове
        загружает данные из файла и сохраняет в кэш. При последующих вызовах возвращает
        данные из кэша.
        
        Returns:
            Словарь с данными о купонах. Ключ - SECID облигации, значение - словарь
            с данными облигации из секции "bonds" файла coupons_data.json.
            Если файл не существует или произошла ошибка при загрузке, возвращает
            пустой словарь.
        """
        if self._coupons_cache is not None:
            return self._coupons_cache
        
        if not self.coupons_file.exists():
            self._coupons_cache = {}
            return self._coupons_cache
        
        try:
            with open(self.coupons_file, 'rb') as f:
                data = orjson.loads(f.read())
            
            self._coupons_cache = data.get("bonds", {})
        except Exception as e:
            print(f"Warning: Failed to load coupons data: {e}")
            self._coupons_cache = {}
        
        return self._coupons_cache
    
    @staticmethod
    def _parse_date(date_str: str) -> Optional[date]:
        """Парсит строку даты в объект date.
        
        Преобразует строку с датой в формате YYYY-MM-DD в объект date.
        Обрабатывает некорректные значения и специальное значение "0000-00-00".
        
        Args:
            date_str: Строка с датой в формате YYYY-MM-DD.
        
        Returns:
            Объект date или None, если строка некорректна, пуста или равна "0000-00-00".
        """
        if not date_str or date_str == "0000-00-00":
            return None
        
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None
    
    def clear_cache(self) -> None:
        """Очищает кэш данных о купонах.
        
        Сбрасывает внутренний кэш, что приведет к повторной загрузке данных
        из файла при следующем обращении к методу _load_coupons_data().
        """
        self._coupons_cache = None


# Singleton instance
_coupon_loader: Optional[CouponLoader] = None


def init_coupon_loader(data_dir: Path) -> None:
    """Инициализирует singleton экземпляр загрузчика купонов.
    
    Создает глобальный экземпляр CouponLoader с указанной директорией данных.
    Должен быть вызван перед использованием get_coupon_loader().
    
    Args:
        data_dir: Путь к директории с JSON файлами данных.
    """
    global _coupon_loader
    _coupon_loader = CouponLoader(data_dir)


def get_coupon_loader() -> Optional[CouponLoader]:
    """Получает singleton экземпляр загрузчика купонов.
    
    Returns:
        Экземпляр CouponLoader или None, если загрузчик не был инициализирован
        через init_coupon_loader().
    """
    return _coupon_loader

