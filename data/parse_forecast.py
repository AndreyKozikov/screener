#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для парсинга макроэкономического отчёта Банка России из Markdown в JSON.
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Путь к markdown-файлу
MARKDOWN_FILE = Path(__file__).parent / "forecast_251024.md"
OUTPUT_FILE = Path(__file__).parent / "forecast_251024.json"


def parse_date_from_header(content: str) -> str:
    """
    Извлекает дату заседания из заголовка документа.
    Формат: "по итогам заседания ... 24 октября 2025 года"
    Возвращает дату в формате YYYY-MM-DD.
    """
    # Ищем паттерн: число + месяц (в родительном падеже) + год
    months = {
        "января": "01", "февраля": "02", "марта": "03", "апреля": "04",
        "мая": "05", "июня": "06", "июля": "07", "августа": "08",
        "сентября": "09", "октября": "10", "ноября": "11", "декабря": "12"
    }
    
    pattern = r"(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(\d{4})\s+года"
    match = re.search(pattern, content, re.IGNORECASE)
    
    if match:
        day = match.group(1).zfill(2)
        month = months[match.group(2).lower()]
        year = match.group(3)
        return f"{year}-{month}-{day}"
    
    return "2025-10-24"  # Значение по умолчанию


def parse_value(value_str: str) -> Optional[Dict[str, float]]:
    """
    Парсит значение из таблицы.
    Обрабатывает:
    - Одиночные числа: "9,5" -> {"мин": 9.5, "макс": 9.5}
    - Диапазоны: "6,5-7,0" или "6,5–7,0" -> {"мин": 6.5, "макс": 7.0}
    - Отрицательные в скобках: "(-0,5)-0,5" -> {"мин": -0.5, "макс": 0.5}
    - Прочерки: "-" -> None
    """
    if not value_str or value_str.strip() == "-":
        return None
    
    value_str = value_str.strip()
    
    # Заменяем запятую на точку для парсинга
    value_str = value_str.replace(",", ".")
    
    # Обрабатываем отрицательные значения в скобках: (-0,5) -> -0.5
    value_str = re.sub(r"\((-?\d+\.?\d*)\)", r"\1", value_str)
    
    # Ищем диапазон (может быть короткое или длинное тире)
    range_match = re.search(r"(-?\d+\.?\d*)\s*[–-]\s*(-?\d+\.?\d*)", value_str)
    
    if range_match:
        min_val = float(range_match.group(1))
        max_val = float(range_match.group(2))
        return {"мин": min_val, "макс": max_val}
    
    # Одиночное значение
    try:
        num = float(value_str)
        return {"мин": num, "макс": num}
    except ValueError:
        return None


def parse_single_value(value_str: str) -> Optional[float]:
    """
    Парсит одиночное значение (без диапазона) для платёжного баланса.
    Возвращает float или None для прочерков.
    """
    if not value_str or value_str.strip() == "-":
        return None
    
    value_str = value_str.strip().replace(",", ".")
    
    try:
        return float(value_str)
    except ValueError:
        return None


def find_table_section(content: str, section_title: str) -> Optional[str]:
    """
    Находит секцию таблицы по заголовку и возвращает её содержимое.
    """
    lines = content.split("\n")
    start_idx = None
    
    for i, line in enumerate(lines):
        if section_title.lower() in line.lower():
            # Ищем начало таблицы (строка с |)
            for j in range(i + 1, min(i + 10, len(lines))):
                if "|" in lines[j] and "---" not in lines[j]:
                    start_idx = j
                    break
            if start_idx:
                break
    
    if start_idx is None:
        return None
    
    # Собираем строки таблицы до следующего заголовка или конца
    table_lines = []
    for i in range(start_idx, len(lines)):
        line = lines[i].strip()
        if not line:
            continue
        if line.startswith("##"):
            break
        if "|" in line:
            table_lines.append(line)
    
    return "\n".join(table_lines)


def parse_main_indicators_table(table_content: str) -> List[Dict]:
    """
    Парсит таблицу "Основные параметры прогноза".
    Возвращает список словарей по годам.
    """
    lines = [line.strip() for line in table_content.split("\n") if line.strip() and "|" in line]
    
    if not lines:
        return []
    
    # Парсим заголовок для получения годов
    header_line = lines[0]
    # Разбиваем по | и убираем пустые элементы
    all_parts = [p.strip() for p in header_line.split("|")]
    # Первый элемент обычно пустой (начало строки), пропускаем его
    # Остальные элементы - это столбцы таблицы
    header_parts = [p for p in all_parts[1:] if p]
    
    # Извлекаем годы из заголовка
    # В таблице: первый столбец - названия, остальные - годы
    years = []
    for part in header_parts:
        # Ищем год в формате YYYY (может быть с дополнительным текстом вроде "(факт)")
        year_match = re.search(r"(\d{4})", part)
        if year_match:
            year = int(year_match.group(1))
            years.append(year)
    
    # Инициализируем структуру данных по годам
    result = {year: {} for year in years}
    
    # Маппинг названий показателей на ключи JSON с сохранением русских названий
    # Структура: (паттерн_в_таблице, json_ключ, русское_название)
    indicator_mapping = [
        ("Инфляция, в %, декабрь к декабрю предыдущего года", "инфляция_декабрь_к_декабрю", "Инфляция, декабрь к декабрю предыдущего года, %"),
        ("Инфляция, в среднем за год, в %к предыдущему году", "инфляция_среднегодовая", "Инфляция, в среднем за год, %"),
        ("Ключевая ставка, в среднем за год, в %годовых", "ключевая_ставка_средняя", "Ключевая ставка, в среднем за год, % годовых"),
        ("Валовой внутренний продукт", "ввп", "Валовой внутренний продукт, прирост в % к предыдущему году"),
        ("- в %, IV квартал к IV кварталу предыдущего года", "ввп_q4_q4", "ВВП, IV квартал к IV кварталу предыдущего года, %"),
        ("Расходы на конечное потребление", "расходы_конечного_потребления", "Расходы на конечное потребление, прирост в % к предыдущему году"),
        ("- домашних хозяйств", "расходы_домохозяйств", "Расходы домашних хозяйств, прирост в % к предыдущему году"),
        ("Валовое накопление", "валовое_накопление", "Валовое накопление, прирост в % к предыдущему году"),
        ("- основного капитала", "накопление_основного_капитала", "Накопление основного капитала, прирост в % к предыдущему году"),
        ("Экспорт", "экспорт", "Экспорт, прирост в % к предыдущему году"),
        ("Импорт", "импорт", "Импорт, прирост в % к предыдущему году"),
        ("Денежная масса в национальном определении", "денежная_масса", "Денежная масса в национальном определении, прирост в % к предыдущему году"),
        ("Требования банковской системы к экономике в рублях и иностранной валюте", "требования_к_экономике", "Требования банковской системы к экономике, прирост в % к предыдущему году"),
        ("- к организациям", "требования_к_организациям", "Требования к организациям, прирост в % к предыдущему году"),
        ("- к населению, в том числе", "требования_к_населению", "Требования к населению, прирост в % к предыдущему году"),
        ("ипотечные жилищные кредиты", "ипотечные_кредиты", "Ипотечные жилищные кредиты, прирост в % к предыдущему году"),
    ]
    
    # Создаём словарь соответствий для сохранения в JSON
    names_mapping = {}
    
    # Парсим строки данных
    for line in lines[1:]:
        if "---" in line:
            continue
        
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) < 2:
            continue
        
        indicator_name = parts[0]
        
        # Ищем соответствие в маппинге (частичное совпадение)
        json_key = None
        russian_name = None
        for pattern, key, russian in indicator_mapping:
            if pattern in indicator_name:
                json_key = key
                russian_name = russian
                # Сохраняем соответствие для JSON
                names_mapping[key] = russian_name
                break
        
        if not json_key:
            continue
        
        # Парсим значения для каждого года
        # parts[0] - название показателя, parts[1] - первый год, parts[2] - второй год и т.д.
        for i, year in enumerate(years):
            # Индекс в parts: i+1 (потому что parts[0] - это название показателя)
            if i + 1 < len(parts):
                value_str = parts[i + 1]
                parsed_value = parse_value(value_str)
                if parsed_value:
                    result[year][json_key] = parsed_value
    
    # Преобразуем в список словарей
    output = []
    for year in sorted(years):
        year_data = {"год": year}
        year_data.update(result[year])
        output.append(year_data)
    
    return output, names_mapping


def parse_balance_table(table_content: str) -> List[Dict]:
    """
    Парсит таблицу "Показатели платёжного баланса".
    Возвращает список словарей по годам.
    """
    lines = [line.strip() for line in table_content.split("\n") if line.strip() and "|" in line]
    
    if not lines:
        return []
    
    # Парсим заголовок для получения годов
    header_line = lines[0]
    header_parts = [p.strip() for p in header_line.split("|") if p.strip()]
    
    # Извлекаем годы из заголовка
    years = []
    for part in header_parts[1:]:
        year_match = re.search(r"(\d{4})", part)
        if year_match:
            year = int(year_match.group(1))
            years.append(year)
    
    # Инициализируем структуру данных по годам
    result = {year: {} for year in years}
    
    # Маппинг названий показателей на ключи JSON (в порядке появления в таблице)
    # Структура: (паттерн_в_таблице, json_ключ, русское_название)
    indicator_patterns = [
        ("Счет текущих операций", "счёт_текущих_операций", "Счёт текущих операций, млрд долл. США"),
        ("Торговый баланс", "торговый_баланс", "Торговый баланс, млрд долл. США"),
        ("Экспорт", "товарный_экспорт", "Товарный экспорт, млрд долл. США"),  # Первый экспорт - товары
        ("Импорт", "товарный_импорт", "Товарный импорт, млрд долл. США"),    # Первый импорт - товары
        ("Баланс услуг", "баланс_услуг", "Баланс услуг, млрд долл. США"),
        ("Экспорт", "экспорт_услуг", "Экспорт услуг, млрд долл. США"),      # Второй экспорт - услуги
        ("Импорт", "импорт_услуг", "Импорт услуг, млрд долл. США"),       # Второй импорт - услуги
        ("Баланс первичных и вторичных доходов", "баланс_доходов", "Баланс первичных и вторичных доходов, млрд долл. США"),
        ("Сальдо финансового счета, исключая резервные активы", "финансовый_счёт", "Сальдо финансового счета, исключая резервные активы, млрд долл. США"),
        ("Чистое принятие обязательств", "принятие_обязательств", "Чистое принятие обязательств, млрд долл. США"),
        ("Чистое приобретение финансовых активов", "приобретение_финансовых_активов", "Чистое приобретение финансовых активов, исключая резервные активы, млрд долл. США"),
        ("Чистые ошибки и пропуски", "ошибки_и_пропуски", "Чистые ошибки и пропуски, млрд долл. США"),
        ("Изменение резервных активов", "изменение_резервов", "Изменение резервных активов, млрд долл. США"),
        ("Цена нефти", "цена_нефти", "Цена нефти для налогообложения, в среднем за год, долл. США за баррель"),
    ]
    
    # Создаём словарь соответствий для сохранения в JSON
    names_mapping = {}
    
    # Отслеживаем порядок для различения экспорта/импорта товаров и услуг
    export_import_counter = {"Экспорт": 0, "Импорт": 0}
    
    # Парсим строки данных
    for line in lines[1:]:
        if "---" in line:
            continue
        
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) < 2:
            continue
        
        indicator_name = parts[0]
        
        # Определяем ключ JSON
        json_key = None
        
        # Специальная обработка для экспорта/импорта (по порядку появления)
        if indicator_name.strip() == "Экспорт":
            export_import_counter["Экспорт"] += 1
            if export_import_counter["Экспорт"] == 1:
                json_key = "товарный_экспорт"
                russian_name = "Товарный экспорт, млрд долл. США"
            else:
                json_key = "экспорт_услуг"
                russian_name = "Экспорт услуг, млрд долл. США"
            names_mapping[json_key] = russian_name
        elif indicator_name.strip() == "Импорт":
            export_import_counter["Импорт"] += 1
            if export_import_counter["Импорт"] == 1:
                json_key = "товарный_импорт"
                russian_name = "Товарный импорт, млрд долл. США"
            else:
                json_key = "импорт_услуг"
                russian_name = "Импорт услуг, млрд долл. США"
            names_mapping[json_key] = russian_name
        else:
            # Ищем соответствие в маппинге (по порядку для точности)
            for pattern, key, russian in indicator_patterns:
                if pattern in indicator_name:
                    json_key = key
                    russian_name = russian
                    # Сохраняем соответствие для JSON
                    names_mapping[key] = russian_name
                    break
        
        if not json_key:
            continue
        
        # Парсим значения для каждого года
        for i, year in enumerate(years):
            if i + 1 < len(parts):
                value_str = parts[i + 1]
                parsed_value = parse_single_value(value_str)
                if parsed_value is not None:
                    result[year][json_key] = parsed_value
    
    # Преобразуем в список словарей
    output = []
    for year in sorted(years):
        year_data = {"год": year}
        year_data.update(result[year])
        output.append(year_data)
    
    return output, names_mapping


def main():
    """Основная функция скрипта."""
    # Читаем markdown-файл
    with open(MARKDOWN_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Извлекаем дату заседания
    date_meeting = parse_date_from_header(content)
    
    # Находим и парсим первую таблицу
    main_table_content = find_table_section(content, "Основные параметры прогноза")
    if not main_table_content:
        raise ValueError("Не найдена таблица 'Основные параметры прогноза'")
    
    main_indicators, main_names = parse_main_indicators_table(main_table_content)
    
    # Находим и парсим вторую таблицу
    balance_table_content = find_table_section(content, "Показатели платежного баланса")
    if not balance_table_content:
        raise ValueError("Не найдена таблица 'Показатели платёжного баланса'")
    
    balance_indicators, balance_names = parse_balance_table(balance_table_content)
    
    # Объединяем все названия
    all_names = {
        "основные_показатели": main_names,
        "платёжный_баланс": balance_names,
    }
    
    # Читаем существующий JSON файл, если он есть
    existing_data = {}
    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Предупреждение: не удалось прочитать существующий файл: {e}")
            existing_data = {}
    
    # Проверяем, нужно ли мигрировать из старой структуры
    # Старая структура: {"дата_заседания": ..., "названия": ..., "основные_показатели": ...}
    # Новая структура: {"названия": ..., "2025-10-24": {...}}
    if "дата_заседания" in existing_data:
        old_date = existing_data["дата_заседания"]
        # Если данные еще не были мигрированы (нет ключа с датой)
        if old_date not in existing_data:
            # Мигрируем из старой структуры
            migrated_data = {
                "названия": existing_data.get("названия", all_names),
                old_date: {
                    "дата_заседания": old_date,
                    "дата_публикации": existing_data.get("дата_публикации", old_date),
                    "основные_показатели": existing_data.get("основные_показатели", []),
                    "платёжный_баланс": existing_data.get("платёжный_баланс", []),
                }
            }
            existing_data = migrated_data
            print(f"Выполнена миграция из старой структуры для даты: {old_date}")
        else:
            # Удаляем старые ключи верхнего уровня, если они есть
            keys_to_remove = ["дата_заседания", "дата_публикации", "основные_показатели", "платёжный_баланс"]
            for key in keys_to_remove:
                if key in existing_data and key != "названия":
                    del existing_data[key]
            print("Удалены старые ключи верхнего уровня")
    
    # Инициализируем структуру, если файл пустой или не существует
    if not existing_data:
        existing_data = {
            "названия": all_names
        }
    else:
        # Обновляем названия только если их еще нет или они пустые
        if "названия" not in existing_data or not existing_data["названия"]:
            existing_data["названия"] = all_names
        else:
            # Дополняем существующие названия новыми (если появились новые поля)
            for section, names in all_names.items():
                if section not in existing_data["названия"]:
                    existing_data["названия"][section] = names
                else:
                    # Добавляем только новые ключи
                    for key, value in names.items():
                        if key not in existing_data["названия"][section]:
                            existing_data["названия"][section][key] = value
    
    # Формируем данные для текущей даты заседания
    meeting_data = {
        "дата_заседания": date_meeting,
        "дата_публикации": date_meeting,
        "основные_показатели": main_indicators,
        "платёжный_баланс": balance_indicators,
    }
    
    # Добавляем или обновляем данные по дате заседания
    existing_data[date_meeting] = meeting_data
    
    # Сохраняем в JSON-файл
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)
    
    print(f"Данные успешно сохранены в {OUTPUT_FILE}")
    print(f"Добавлена/обновлена запись для даты заседания: {date_meeting}")


if __name__ == "__main__":
    main()

