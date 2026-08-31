"""Модели данных рейтингов для таблиц bond_ratings, rating_agency, emitent_ratings.

Используются для запросов к БД через SQLModel select/join в BondTransformer.
Соответствуют миграциям Alembic: 006 (rating_agency), 009 (emitent_ratings), 011 (bond_ratings).
"""

from typing import Optional

from sqlmodel import SQLModel, Field as SQLField, UniqueConstraint


class RatingAgency(SQLModel, table=True):
    """Справочник рейтинговых агентств (таблица rating_agency).

    Миграция 006: id, agency_id (UNIQUE), agency_name_short_ru, agency_name_full_ru, is_system.
    """

    __tablename__ = "rating_agency"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    agency_id: int = SQLField(unique=True)
    agency_name_short_ru: str = SQLField(max_length=64)
    agency_name_full_ru: Optional[str] = SQLField(default=None, max_length=256)
    is_system: int = SQLField(default=0)


class BondRating(SQLModel, table=True):
    """Рейтинги облигаций (таблица bond_ratings).

    Миграция 011: bond_id (FK bonds.id), agency_id (FK rating_agency.agency_id),
    rating_level_name, rating_date. JOIN с RatingAgency по agency_id = rating_agency.agency_id.
    """

    __tablename__ = "bond_ratings"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    bond_id: int = SQLField(foreign_key="bonds.id")
    agency_id: int = SQLField()  # значение из rating_agency.agency_id (не PK)
    rating_level_name: str = SQLField()
    rating_date: Optional[str] = SQLField(default=None)


class EmitentRating(SQLModel, table=True):
    """Рейтинги эмитентов (таблица emitent_ratings).

    Миграция 009: emitent_id (FK emitents.id), agency_id (FK rating_agency.id),
    rating_level_name, rating_date, rating_publicate_date.
    """

    __tablename__ = "emitent_ratings"
    __table_args__ = (
        UniqueConstraint("emitent_id", "agency_id", name="uq_emitent_ratings_emitent_agency"),
    )

    id: Optional[int] = SQLField(default=None, primary_key=True)
    emitent_id: int = SQLField(foreign_key="emitents.id")
    agency_id: int = SQLField(foreign_key="rating_agency.id")
    rating_level_name: Optional[str] = SQLField(default=None)
    rating_date: Optional[str] = SQLField(default=None)
    rating_publicate_date: Optional[str] = SQLField(default=None)
