"""Сервис runtime-настроек приложения.

Позволяет менять часть параметров из конфигурационных файлов
(backend/config/settings.py и backend/config/config_llm.toml) без правки
кода и без ручного редактирования .env:

- переопределения хранятся в JSON-файле ``backend/app/data/runtime_settings.json``;
- при старте (init_runtime_settings) переопределения применяются к глобальному
  объекту ``config.settings.settings``, поэтому все существующие сервисы,
  читающие ``settings.*``, сразу получают актуальные значения;
- через PUT /api/settings значения можно менять «на лету» без перезапуска
  (кроме настроек, помеченных ``restart=True`` — например, AGENT_ENABLED,
  который читается при регистрации роутеров в main.py).

Каждая настройка описывается спецификацией SettingSpec: ключ, заголовок,
подробное описание (для подсказки на странице настроек), тип значения,
группа (вкладка), значение по умолчанию, функции чтения и применения.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from config import paths
from config.settings import settings
from app.macro_dashboard.config import ACTIVE_CONFIG, DEFAULT_CONFIG

logger = logging.getLogger(__name__)

# Файл переопределений. DATA_DIR = backend/app/data (см. config.paths).
PERSIST_PATH: Path = paths.DATA_DIR / "runtime_settings.json"

# Типы значений, поддерживаемые страницей настроек.
VALUE_TYPE_BOOLEAN = "boolean"
VALUE_TYPE_INTEGER = "integer"
VALUE_TYPE_NUMBER = "number"
VALUE_TYPE_TEXT = "text"
VALUE_TYPE_SECRET = "secret"
VALUE_TYPE_SELECT = "select"
VALUE_TYPE_MULTISELECT = "multiselect"


@dataclass
class SettingSpec:
    """Описание одной настройки, доступной для изменения через UI."""

    key: str
    label: str
    description: str
    group: str
    value_type: str
    default: Any
    load: Callable[[], Any]
    apply: Callable[[Any], None]
    options: Optional[List[Dict[str, str]]] = None
    restart: bool = False
    secret: bool = False
    section: Optional[str] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None


_MACRO_SETTING_BINDINGS: Dict[str, Tuple[str, Optional[str]]] = {}
_MACRO_WEIGHT_GROUPS = (
    "inflation_weights",
    "expectations_weights",
    "monetary_weights",
    "market_weights",
    "direction_weights",
)


# ── Группы (вкладки страницы настроек) ─────────────────────────────────────────

GROUPS: List[Dict[str, str]] = [
    {
        "id": "agent",
        "title": "ИИ-агент подбора облигаций",
        "description": (
            "Параметры ИИ-агента: включение фичи, выбор LLM-провайдера, "
            "которым агент отвечает пользователю, и логирование диалогов."
        ),
    },
    {
        "id": "providers",
        "title": "Провайдеры LLM (config_llm.toml)",
        "description": (
            "Список удалённых LLM-провайдеров и привязанные к ним модели. "
            "Порядок списка задаёт очерёдность перебора в режиме AUTO."
        ),
    },
    {
        "id": "local",
        "title": "Локальная LLM (Qwen3-4B)",
        "description": (
            "Адрес и параметры запросов к локальной модели, которая используется "
            "для анализа документации и расчёта параметров флоатеров без внешних API."
        ),
    },
    {
        "id": "services",
        "title": "Внешние сервисы и анализ",
        "description": (
            "Адреса вспомогательных сервисов (конвертация PDF, репозиторий данных), "
            "источник списка облигаций Мосбиржи, заголовки OpenRouter и лимиты анализа."
        ),
    },
    {
        "id": "macro_dashboard",
        "title": "Макродашборд",
        "description": (
            "Пороги классификации сигналов, веса показателей и веса четырёх направлений. "
            "Изменения применяются сразу и сохраняются на сервере."
        ),
    },
    {
        "id": "keys",
        "title": "Ключи API",
        "description": (
            "API-ключи облачных провайдеров. Хранятся локально в файле "
            "runtime_settings.json и переопределяют значения из .env. "
            "Поле показывается пустым: введите новый ключ, чтобы его заменить, "
            "или оставьте пустым, чтобы не менять."
        ),
    },
]


# ── Внутреннее состояние ───────────────────────────────────────────────────────

_SPECS: List[SettingSpec] = []
_SPECS_BY_KEY: Dict[str, SettingSpec] = {}
_DEFAULTS: Dict[str, Any] = {}
_OVERRIDES: Dict[str, Any] = {}


# ── Спецификации настроек ──────────────────────────────────────────────────────

def _bool_apply(attr: str) -> Callable[[Any], None]:
    def _apply(value: Any) -> None:
        setattr(settings, attr, _to_bool(value))
    return _apply


def _str_apply(attr: str) -> Callable[[Any], None]:
    def _apply(value: Any) -> None:
        setattr(settings, attr, str(value))
    return _apply


def _int_apply(attr: str) -> Callable[[Any], None]:
    def _apply(value: Any) -> None:
        setattr(settings, attr, int(value))
    return _apply


def _float_apply(attr: str) -> Callable[[Any], None]:
    def _apply(value: Any) -> None:
        setattr(settings, attr, float(value))
    return _apply


def _secret_apply(attr: str) -> Callable[[Any], None]:
    """Применяет секрет только если передано непустое значение."""
    def _apply(value: Any) -> None:
        raw = str(value or "").strip()
        if raw:
            setattr(settings, attr, raw)
    return _apply


def _provider_model_apply(name: str) -> Callable[[Any], None]:
    """Применяет новую модель для конкретного провайдера из config_llm.toml."""
    def _apply(value: Any) -> None:
        if settings.llm is not None and name in settings.llm.providers:
            settings.llm.providers[name].model = str(value)
    return _apply


def _enabled_providers_apply(value: Any) -> None:
    """Заменяет remote_providers (порядок перебора в режиме AUTO)."""
    if settings.llm is None:
        return
    names = [str(v) for v in (value or [])]
    settings.llm.remote_providers = [n for n in names if n in settings.llm.providers]


def _macro_config_apply(attribute: str, item: Optional[str] = None) -> Callable[[Any], None]:
    def _apply(value: Any) -> None:
        numeric_value = float(value)
        if item is None:
            setattr(ACTIVE_CONFIG, attribute, numeric_value)
        else:
            getattr(ACTIVE_CONFIG, attribute)[item] = numeric_value
    return _apply


def _append_macro_dashboard_specs(specs: List[SettingSpec]) -> None:
    def add_scalar(
        attribute: str,
        label: str,
        description: str,
        section: str,
        *,
        minimum: float,
        maximum: float,
    ) -> None:
        key = f"macro_dashboard.{attribute}"
        _MACRO_SETTING_BINDINGS[key] = (attribute, None)
        specs.append(SettingSpec(
            key=key,
            label=label,
            description=description,
            group="macro_dashboard",
            section=section,
            value_type=VALUE_TYPE_NUMBER,
            default=getattr(DEFAULT_CONFIG, attribute),
            load=lambda attr=attribute: getattr(ACTIVE_CONFIG, attr),
            apply=_macro_config_apply(attribute),
            minimum=minimum,
            maximum=maximum,
        ))

    def add_mapping(
        attribute: str,
        item: str,
        label: str,
        description: str,
        section: str,
        *,
        minimum: float,
        maximum: float,
    ) -> None:
        key = f"macro_dashboard.{attribute}.{item}"
        _MACRO_SETTING_BINDINGS[key] = (attribute, item)
        specs.append(SettingSpec(
            key=key,
            label=label,
            description=description,
            group="macro_dashboard",
            section=section,
            value_type=VALUE_TYPE_NUMBER,
            default=getattr(DEFAULT_CONFIG, attribute)[item],
            load=lambda attr=attribute, name=item: getattr(ACTIVE_CONFIG, attr)[name],
            apply=_macro_config_apply(attribute, item),
            minimum=minimum,
            maximum=maximum,
        ))

    indicator_labels = {
        "inflation_mom": "Инфляция за месяц",
        "inflation_yoy": "Инфляция за 12 месяцев",
        "inflation_weekly": "Недельная инфляция",
        "trend_inflation_3y": "Трендовая инфляция, 3 года",
        "trend_inflation_5y": "Трендовая инфляция, 5 лет",
        "modified_core_inflation": "Модифицированная базовая инфляция",
        "expectations_1y": "Ожидания на 1 год",
        "expectations_5y": "Ожидания на 5 лет",
        "ruonia_change_30d": "Изменение RUONIA за 30 дней",
        "key_rate_change_30d": "Изменение ключевой ставки за 30 дней",
        "spread_change_30d": "Изменение спреда RUONIA за 30 дней",
        "yield_2y_change_30d": "Изменение доходности ОФЗ 2 года за 30 дней",
        "yield_5y_change_30d": "Изменение доходности ОФЗ 5 лет за 30 дней",
        "yield_10y_change_30d": "Изменение доходности ОФЗ 10 лет за 30 дней",
        "inflation": "Инфляция",
        "expectations": "Инфляционные ожидания",
        "monetary_conditions": "Денежно-кредитные условия",
        "bond_market": "Рынок ОФЗ",
    }

    for item in DEFAULT_CONFIG.inflation_thresholds:
        add_mapping(
            "inflation_thresholds", item,
            f"Порог стабильности: {indicator_labels[item]}",
            "Минимальная разница между средним значением последних трёх периодов и предыдущих трёх, считающаяся значимым изменением, п.п.",
            "Пороги сигналов",
            minimum=0,
            maximum=100,
        )
    add_scalar(
        "expectations_threshold_pp",
        "Порог изменения инфляционных ожиданий",
        "Минимальное изменение среднего за последние три месяца относительно предыдущих трёх, считающееся значимым, п.п.",
        "Пороги сигналов",
        minimum=0,
        maximum=100,
    )
    add_scalar(
        "monetary_threshold_pp",
        "Порог изменения денежно-кредитных условий",
        "Минимальное изменение ставок или спреда за 30 дней, считающееся значимым, п.п.",
        "Пороги сигналов",
        minimum=0,
        maximum=100,
    )
    add_scalar(
        "market_threshold_pp",
        "Порог изменения доходностей ОФЗ",
        "Минимальное изменение доходности за 30 дней, считающееся значимым, п.п.",
        "Пороги сигналов",
        minimum=0,
        maximum=100,
    )

    weight_sections = (
        ("inflation_weights", "Вес инфляционного показателя"),
        ("expectations_weights", "Вес показателя ожиданий"),
        ("monetary_weights", "Вес показателя денежного рынка"),
        ("market_weights", "Вес доходности ОФЗ"),
    )
    for attribute, label_prefix in weight_sections:
        for item in getattr(DEFAULT_CONFIG, attribute):
            add_mapping(
                attribute,
                item,
                f"{label_prefix}: {indicator_labels[item]}",
                "Относительный вес этого показателя внутри соответствующего направления. Ноль исключает показатель из расчёта.",
                "Веса показателей",
                minimum=0,
                maximum=1,
            )

    for item in DEFAULT_CONFIG.direction_weights:
        add_mapping(
            "direction_weights", item,
            f"Вес направления: {indicator_labels[item]}",
            "Относительный вес направления в итоговом индексе и балансе аргументов.",
            "Веса направлений",
            minimum=0,
            maximum=1,
        )

    for item in DEFAULT_CONFIG.minimum_coverage:
        add_mapping(
            "minimum_coverage", item,
            f"Минимальное покрытие: {indicator_labels[item]}",
            "Минимальная доля доступного веса показателей направления, необходимая для классификации, от 0 до 1.",
            "Покрытие данных",
            minimum=0,
            maximum=1,
        )
    add_scalar(
        "total_minimum_coverage",
        "Минимальное покрытие итогового индекса",
        "Минимальная доля веса направлений с достаточными данными, необходимая для расчёта общего индекса, от 0 до 1.",
        "Покрытие данных",
        minimum=0,
        maximum=1,
    )
    add_scalar(
        "score_threshold",
        "Порог классификации балла",
        "Граница балла от 0 до 1 для статуса «за снижение» или «за повышение».",
        "Пороги итоговой оценки",
        minimum=0,
        maximum=1,
    )
    add_scalar(
        "mixed_signal_share",
        "Минимальная доля разнонаправленных сигналов",
        "Доля доступного веса каждого из противоположных знаков, при которой направление можно назвать смешанным, от 0 до 0,5.",
        "Пороги итоговой оценки",
        minimum=0,
        maximum=0.5,
    )


# Человекочитаемые названия моделей для списка выбора LLM ИИ-агента.
_MODEL_FRIENDLY_LABELS: Dict[str, str] = {
    "gemini-2.5-flash-lite": "Gemini 2.5 Flash Lite",
    "gemini-2.5-flash": "Gemini 2.5 Flash",
    "gemini-2.5-pro": "Gemini 2.5 Pro",
    "gemini-2.0-flash": "Gemini 2.0 Flash",
    "gemini-3-flash-preview": "Gemini 3 Flash",
    "gemini-3.1-pro-preview": "Gemini 3.1 Pro",
    "gpt-5.1": "GPT-5.1",
    "gpt-4o": "GPT-4o",
    "gpt-4o-mini": "GPT-4o Mini",
    "deepseek/deepseek-v4-pro": "DeepSeek v4 Pro",
}


def _agent_provider_options() -> List[Dict[str, str]]:
    """Список моделей для ИИ-агента: AUTO + каждый провайдер с понятным названием.

    Значение — имя провайдера из config_llm.toml (читается как AGENT_PROVIDER),
    подпись — провайдер и его модель в человекочитаемом виде.
    """
    options = [{"value": "", "label": "AUTO — автоматический выбор модели"}]
    if settings.llm is not None:
        for name in settings.llm.providers.keys():
            provider = settings.llm.providers[name]
            model = getattr(provider, "model", "") or name
            label = _MODEL_FRIENDLY_LABELS.get(model, model)
            options.append({"value": name, "label": f"{name} — {label}"})
    return options


def _build_specs() -> List[SettingSpec]:
    """Строит список спецификаций на основе текущей конфигурации.

    Вызывается при инициализации: набор провайдеров и их моделей берётся из
    config_llm.toml (через settings.llm), поэтому спецификации провайдеров
    генерируются динамически.
    """
    specs: List[SettingSpec] = []

    # ── ИИ-агент ──
    specs.append(SettingSpec(
        key="agent_enabled",
        label="Включить ИИ-агента",
        description=(
            "Отвечает за доступность раздела «Чат с ИИ» и роутера /api/agent/chat. "
            "Значение читается при старте бэкенда, поэтому применяется только "
            "после перезапуска (restart)."
        ),
        group="agent",
        value_type=VALUE_TYPE_BOOLEAN,
        default=settings.AGENT_ENABLED,
        load=lambda: bool(settings.AGENT_ENABLED),
        apply=_bool_apply("AGENT_ENABLED"),
        restart=True,
    ))
    specs.append(SettingSpec(
        key="agent_provider",
        label="LLM-провайдер для агента",
        description=(
            "Провайдер (имя из config_llm.toml), через который ИИ-агент вызывает модель. "
            "AUTO — перебор доступных провайдеров по порядку с фолбэком: если первый "
            "не ответил (квота, сеть), вызов уходит следующему."
        ),
        group="agent",
        value_type=VALUE_TYPE_SELECT,
        default=settings.AGENT_PROVIDER,
        load=lambda: settings.AGENT_PROVIDER,
        apply=_str_apply("AGENT_PROVIDER"),
        options=_agent_provider_options,
    ))
    specs.append(SettingSpec(
        key="agent_log_enabled",
        label="Логировать диалоги агента",
        description=(
            "Писать запросы, уточнения пользователя и ответы модели в отдельную папку. "
            "Удобно для отладки и аудита работы агента."
        ),
        group="agent",
        value_type=VALUE_TYPE_BOOLEAN,
        default=settings.AGENT_LOG_ENABLED,
        load=lambda: bool(settings.AGENT_LOG_ENABLED),
        apply=_bool_apply("AGENT_LOG_ENABLED"),
    ))
    specs.append(SettingSpec(
        key="agent_log_dir",
        label="Папка логов сессий агента",
        description=(
            "Каталог, куда пишутся сессии агента, когда включено логирование. "
            "Путь относителен к корню backend."
        ),
        group="agent",
        value_type=VALUE_TYPE_TEXT,
        default=settings.AGENT_LOG_DIR,
        load=lambda: settings.AGENT_LOG_DIR,
        apply=_str_apply("AGENT_LOG_DIR"),
    ))

    # ── Провайдеры LLM (config_llm.toml) ──
    if settings.llm is not None:
        provider_options = [
            {"value": name, "label": name} for name in settings.llm.providers.keys()
        ]
        specs.append(SettingSpec(
            key="providers_enabled",
            label="Активные провайдеры (порядок перебора AUTO)",
            description=(
                "Какие провайдеры участвуют в автоматическом переборе и в каком порядке. "
                "Модель каждого провайдера задаётся ниже."
            ),
            group="providers",
            value_type=VALUE_TYPE_MULTISELECT,
            default=list(settings.llm.remote_providers),
            load=lambda: list(settings.llm.remote_providers),
            apply=_enabled_providers_apply,
            options=provider_options,
        ))
        for name, provider in settings.llm.providers.items():
            specs.append(SettingSpec(
                key=f"provider_model.{name}",
                label=f"Модель провайдера «{name}»",
                description=(
                    f"Идентификатор модели, используемой провайдером {name} "
                    f"(тип: {provider.type}). Применяется сразу ко всем вызовам, "
                    "которые используют этого провайдера."
                ),
                group="providers",
                value_type=VALUE_TYPE_TEXT,
                default=provider.model,
                load=(lambda n=name: settings.llm.providers[n].model if settings.llm and n in settings.llm.providers else ""),
                apply=_provider_model_apply(name),
            ))

    # ── Локальная LLM ──
    specs.append(SettingSpec(
        key="local_llm_base_url",
        label="Базовый URL локальной модели",
        description=(
            "Адрес сервера локальной LLM (например, vLLM или Ollama-совместимого API). "
            "Используется в пайплайнах анализа документов и расчёта флоатеров."
        ),
        group="local",
        value_type=VALUE_TYPE_TEXT,
        default=settings.LOCAL_LLM_BASE_URL,
        load=lambda: settings.LOCAL_LLM_BASE_URL,
        apply=_str_apply("LOCAL_LLM_BASE_URL"),
    ))
    specs.append(SettingSpec(
        key="local_llm_generate_path",
        label="Путь эндпоинта генерации",
        description=(
            "URL-путь (относительно base_url) к эндпоинту генерации локальной модели. "
            "Полный адрес формируется как base_url + generate_path."
        ),
        group="local",
        value_type=VALUE_TYPE_TEXT,
        default=settings.LOCAL_LLM_GENERATE_PATH,
        load=lambda: settings.LOCAL_LLM_GENERATE_PATH,
        apply=_str_apply("LOCAL_LLM_GENERATE_PATH"),
    ))
    specs.append(SettingSpec(
        key="local_llm_max_new_tokens",
        label="Максимум новых токенов",
        description=(
            "Ограничение длины ответа локальной модели (max_new_tokens) при анализе. "
            "Слишком маленькое значение обрезает развёрнутые ответы."
        ),
        group="local",
        value_type=VALUE_TYPE_INTEGER,
        default=settings.LOCAL_LLM_ANALYSIS_MAX_NEW_TOKENS,
        load=lambda: settings.LOCAL_LLM_ANALYSIS_MAX_NEW_TOKENS,
        apply=_int_apply("LOCAL_LLM_ANALYSIS_MAX_NEW_TOKENS"),
    ))
    specs.append(SettingSpec(
        key="local_llm_temperature",
        label="Temperature (креативность)",
        description=(
            "Температура сэмплирования: меньше — строже и детерминированнее, "
            "больше — разнообразнее, но рискованнее для расчётов."
        ),
        group="local",
        value_type=VALUE_TYPE_NUMBER,
        default=settings.LOCAL_LLM_ANALYSIS_TEMPERATURE,
        load=lambda: settings.LOCAL_LLM_ANALYSIS_TEMPERATURE,
        apply=_float_apply("LOCAL_LLM_ANALYSIS_TEMPERATURE"),
    ))
    specs.append(SettingSpec(
        key="local_llm_top_p",
        label="Top-P (ядро вероятностей)",
        description=(
            "Nucleus sampling: учитываются только токены, накопительная вероятность "
            "которых не превышает top_p. Рекомендуемый диапазон 0.8–1.0."
        ),
        group="local",
        value_type=VALUE_TYPE_NUMBER,
        default=settings.LOCAL_LLM_ANALYSIS_TOP_P,
        load=lambda: settings.LOCAL_LLM_ANALYSIS_TOP_P,
        apply=_float_apply("LOCAL_LLM_ANALYSIS_TOP_P"),
    ))

    # ── Внешние сервисы и анализ ──
    specs.append(SettingSpec(
        key="db_repository_url",
        label="URL репозитория данных",
        description=(
            "Базовый адрес отдельного сервиса-репозитория (db_repository), "
            "через который BondsScreener читает облигации, купоны и рейтинги."
        ),
        group="services",
        value_type=VALUE_TYPE_TEXT,
        default=settings.DB_REPOSITORY_URL,
        load=lambda: settings.DB_REPOSITORY_URL,
        apply=_str_apply("DB_REPOSITORY_URL"),
    ))
    specs.append(SettingSpec(
        key="openrouter_http_referer",
        label="OpenRouter: HTTP-Referer",
        description=(
            "Заголовок HTTP-Referer, отправляемый в OpenRouter (например, адрес "
            "приложения). Некоторые бесплатные модели требуют его указания."
        ),
        group="services",
        value_type=VALUE_TYPE_TEXT,
        default=settings.OPENROUTER_HTTP_REFERER,
        load=lambda: settings.OPENROUTER_HTTP_REFERER,
        apply=_str_apply("OPENROUTER_HTTP_REFERER"),
    ))
    specs.append(SettingSpec(
        key="openrouter_x_title",
        label="OpenRouter: X-OpenRouter-Title",
        description=(
            "Название приложения, которое OpenRouter показывает в статистике "
            "использования (заголовок X-OpenRouter-Title)."
        ),
        group="services",
        value_type=VALUE_TYPE_TEXT,
        default=settings.OPENROUTER_X_TITLE,
        load=lambda: settings.OPENROUTER_X_TITLE,
        apply=_str_apply("OPENROUTER_X_TITLE"),
    ))
    specs.append(SettingSpec(
        key="floater_analysis_prompt_max_chars",
        label="Лимит промпта анализа флоатеров",
        description=(
            "Максимальная длина текста, который отправляется в LLM при анализе "
            "флоатеров. Превышающая часть обрезается, чтобы уложиться в контекст модели."
        ),
        group="services",
        value_type=VALUE_TYPE_INTEGER,
        default=settings.FLOATER_ANALYSIS_PROMPT_MAX_CHARS,
        load=lambda: settings.FLOATER_ANALYSIS_PROMPT_MAX_CHARS,
        apply=_int_apply("FLOATER_ANALYSIS_PROMPT_MAX_CHARS"),
    ))

    # ── Ключи API ──
    specs.append(SettingSpec(
        key="openai_api_key",
        label="OpenAI API Key",
        description=(
            "Ключ для провайдера OpenAI (GPT). Переопределяет OPENAI_API_KEY из .env. "
            "Не передаётся в интерфейс — введите новый ключ, чтобы заменить текущий."
        ),
        group="keys",
        value_type=VALUE_TYPE_SECRET,
        default="",
        load=lambda: settings.OPENAI_API_KEY,
        apply=_secret_apply("OPENAI_API_KEY"),
        secret=True,
    ))
    specs.append(SettingSpec(
        key="gemini_api_key",
        label="Google Gemini API Key",
        description=(
            "Ключ для провайдера Google Gemini. Переопределяет GEMINI_API_KEY из .env."
        ),
        group="keys",
        value_type=VALUE_TYPE_SECRET,
        default="",
        load=lambda: settings.GEMINI_API_KEY,
        apply=_secret_apply("GEMINI_API_KEY"),
        secret=True,
    ))
    specs.append(SettingSpec(
        key="openrouter_api_key",
        label="OpenRouter API Key",
        description=(
            "Ключ для провайдера OpenRouter. Переопределяет OPENROUTER_API_KEY из .env."
        ),
        group="keys",
        value_type=VALUE_TYPE_SECRET,
        default="",
        load=lambda: settings.OPENROUTER_API_KEY,
        apply=_secret_apply("OPENROUTER_API_KEY"),
        secret=True,
    ))

    _append_macro_dashboard_specs(specs)
    return specs


# ── Вспомогательные функции ────────────────────────────────────────────────────

def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on", "да"}


def _load_overrides() -> Dict[str, Any]:
    if not PERSIST_PATH.exists():
        return {}
    try:
        with open(PERSIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        logger.warning("Не удалось прочитать %s — переопределения игнорируются", PERSIST_PATH)
        return {}


def _persist_overrides() -> None:
    try:
        PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(PERSIST_PATH, "w", encoding="utf-8") as f:
            json.dump(_OVERRIDES, f, ensure_ascii=False, indent=2)
    except OSError:
        logger.exception("Не удалось сохранить runtime-настройки в %s", PERSIST_PATH)


def _coerce(spec: SettingSpec, value: Any) -> Any:
    """Приводит значение из запроса к типу настройки."""
    if spec.value_type == VALUE_TYPE_BOOLEAN:
        return _to_bool(value)
    if spec.value_type == VALUE_TYPE_INTEGER:
        try:
            numeric_value = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"Настройка «{spec.label}» ожидает целое число, получено: {value!r}")
        return _validate_numeric_range(spec, numeric_value)
    if spec.value_type == VALUE_TYPE_NUMBER:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Настройка «{spec.label}» ожидает число, получено: {value!r}")
        return _validate_numeric_range(spec, numeric_value)
    if spec.value_type == VALUE_TYPE_MULTISELECT:
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        if isinstance(value, (list, tuple)):
            return [str(v) for v in value]
        raise ValueError(f"Настройка «{spec.label}» ожидает список значений")
    return value


def _validate_numeric_range(spec: SettingSpec, value: int | float) -> int | float:
    if not math.isfinite(float(value)):
        raise ValueError(f"Настройка «{spec.label}» должна быть конечным числом")
    if spec.minimum is not None and value < spec.minimum:
        raise ValueError(f"Настройка «{spec.label}» должна быть не меньше {spec.minimum}")
    if spec.maximum is not None and value > spec.maximum:
        raise ValueError(f"Настройка «{spec.label}» должна быть не больше {spec.maximum}")
    return value


# ── Публичное API сервиса ──────────────────────────────────────────────────────

def init_runtime_settings() -> None:
    """Загружает переопределения и применяет их к глобальному settings.

    Вызывается один раз при старте приложения (в lifespan), до инициализации
    остальных сервисов, чтобы те сразу видели актуальные значения.
    """
    global _SPECS, _SPECS_BY_KEY, _DEFAULTS, _OVERRIDES
    _SPECS = _build_specs()
    _SPECS_BY_KEY = {spec.key: spec for spec in _SPECS}
    _DEFAULTS = {spec.key: spec.load() for spec in _SPECS}
    _OVERRIDES = _load_overrides()
    _apply_overrides()


def get_schema() -> Dict[str, Any]:
    """Возвращает описание настроек для страницы интерфейса.

    Структура: groups -> fields. Для секретных полей value всегда пустая
    строка (сам ключ не отдаётся в UI), вместо него — флаг is_set.
    """
    groups: Dict[str, List[Dict[str, Any]]] = {g["id"]: [] for g in GROUPS}
    for spec in _SPECS:
        if spec.secret:
            current = ""
            is_set = bool(spec.load())
        else:
            current = spec.load()
            is_set = None
        options = None
        if callable(spec.options):
            options = spec.options()
        elif spec.options is not None:
            options = spec.options
        groups[spec.group].append({
            "key": spec.key,
            "label": spec.label,
            "description": spec.description,
            "type": spec.value_type,
            "value": current,
            "default": _DEFAULTS.get(spec.key),
            "options": options,
            "restart": spec.restart,
            "secret": spec.secret,
            "is_set": is_set,
            "section": spec.section,
            "minimum": spec.minimum,
            "maximum": spec.maximum,
        })

    return {
        "groups": [
            {"id": g["id"], "title": g["title"], "description": g["description"], "fields": groups[g["id"]]}
            for g in GROUPS
        ]
    }


def update_runtime_settings(updates: Dict[str, Any]) -> None:
    """Применяет и сохраняет переопределения.

    Пустое значение для секретных полей интерпретируется как «не менять».
    """
    _validate_macro_weight_updates(updates)
    for key, value in updates.items():
        spec = _SPECS_BY_KEY.get(key)
        if spec is None:
            raise ValueError(f"Неизвестная настройка: {key!r}")
        coerced = _coerce(spec, value)
        if spec.secret:
            raw = str(coerced or "").strip()
            if not raw:
                continue
            _OVERRIDES[key] = raw
        else:
            _OVERRIDES[key] = coerced
        spec.apply(coerced)
    _persist_overrides()


def _validate_macro_weight_updates(updates: Dict[str, Any]) -> None:
    candidates = {
        attribute: dict(getattr(ACTIVE_CONFIG, attribute))
        for attribute in _MACRO_WEIGHT_GROUPS
    }
    for key, value in updates.items():
        binding = _MACRO_SETTING_BINDINGS.get(key)
        if binding is None:
            continue
        attribute, item = binding
        if attribute not in candidates or item is None:
            continue
        spec = _SPECS_BY_KEY.get(key)
        if spec is None:
            continue
        candidates[attribute][item] = _coerce(spec, value)

    labels = {
        "inflation_weights": "инфляции",
        "expectations_weights": "инфляционных ожиданий",
        "monetary_weights": "денежно-кредитных условий",
        "market_weights": "рынка ОФЗ",
        "direction_weights": "макроэкономических направлений",
    }
    for attribute, weights in candidates.items():
        if sum(weights.values()) <= 0:
            raise ValueError(f"Сумма весов {labels[attribute]} должна быть больше нуля")


def reset_runtime_settings() -> None:
    """Сбрасывает все переопределения и возвращает значения из конфигурации."""
    global _OVERRIDES
    _OVERRIDES = {}
    if PERSIST_PATH.exists():
        try:
            PERSIST_PATH.unlink()
        except OSError:
            logger.exception("Не удалось удалить %s", PERSIST_PATH)
    for spec in _SPECS:
        if spec.secret:
            continue
        try:
            spec.apply(_DEFAULTS.get(spec.key))
        except Exception:
            logger.exception("Не удалось сбросить настройку %s", spec.key)
    _persist_overrides()


def _apply_overrides() -> None:
    for key, value in _OVERRIDES.items():
        spec = _SPECS_BY_KEY.get(key)
        if spec is None:
            continue
        try:
            spec.apply(value)
        except Exception:
            logger.exception("Не удалось применить runtime-настройку %s", key)
