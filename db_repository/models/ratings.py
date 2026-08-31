from typing import Optional

from sqlmodel import SQLModel, Field as SQLField, UniqueConstraint


class BondRatingBase(SQLModel):
    bond_id: int = SQLField(foreign_key="bonds.id")
    agency_id: int = SQLField()  # значение из rating_agency.agency_id (не PK)
    rating_level_name: str = SQLField()
    rating_date: Optional[str] = SQLField(default=None)


class BondRating(BondRatingBase, table=True):
    __tablename__ = "bond_ratings"
    id: Optional[int] = SQLField(default=None, primary_key=True)


class EmitentRatingBase(SQLModel):
    agency_id: int = SQLField(foreign_key="rating_agency.id", validation_alias="agency_id")
    rating_level_name: Optional[str] = SQLField(default=None, validation_alias="rating_level_name_short_ru")
    rating_date: Optional[str] = SQLField(default=None, validation_alias="rating_date")
    rating_publicate_date: Optional[str] = SQLField(default=None, validation_alias="rating_publicate_date")


class EmitentRating(EmitentRatingBase, table=True):
    __tablename__ = "emitent_ratings"
    __table_args__ = (
        UniqueConstraint("emitent_id", "agency_id", name="uq_emitent_ratings_emitent_agency"),
    )
    id: Optional[int] = SQLField(default=None, primary_key=True)
    emitent_id: int = SQLField(foreign_key="emitents.id",
                               ondelete="CASCADE")


class RatingAgency(SQLModel, table=True):
    __tablename__ = "rating_agency"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    agency_id: int = SQLField(unique=True)
    agency_name_short_ru: str = SQLField(max_length=64)
    agency_name_full_ru: Optional[str] = SQLField(default=None, max_length=256)
    is_system: int = SQLField(default=0)
