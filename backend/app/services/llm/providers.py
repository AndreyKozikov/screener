# app/services/llm/providers.py
import importlib
import pkgutil
from pathlib import Path

# Определяем путь к текущей папке с провайдерами
_current_dir = str(Path(__file__).parent)

# Автоматически находим и импортируем все .py файлы в этой папке
for _, module_name, _ in pkgutil.iter_modules([_current_dir]):
    # Исключаем сам файл реестра, базу и текущий файл сборщика
    if module_name not in ["base", "registry", "providers"]:
        importlib.import_module(f"app.services.llm.{module_name}")