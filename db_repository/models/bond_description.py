"""MOEX description fields associated with a bond and its issuer."""

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import ConfigDict, field_validator
from sqlalchemy import BigInteger, Boolean, Date, Integer, Numeric, String, Text
from sqlmodel import Field as SQLField, SQLModel


class BondDescriptionBase(SQLModel):
    """Validated MOEX description values using lowercase database field names."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    bond_id: int = SQLField(
        primary_key=True,
        foreign_key="bonds.id",
        ondelete="CASCADE",
    )
    issuename: Optional[str] = SQLField(default=None, sa_type=Text, validation_alias="ISSUENAME")
    regnumber: Optional[str] = SQLField(default=None, sa_type=String, validation_alias="REGNUMBER")
    issuedate: Optional[date] = SQLField(default=None, sa_type=Date, validation_alias="ISSUEDATE")
    matdate: Optional[date] = SQLField(default=None, sa_type=Date, validation_alias="MATDATE")
    initialfacevalue: Optional[Decimal] = SQLField(
        default=None, sa_type=Numeric(15, 2), validation_alias="INITIALFACEVALUE"
    )
    faceunit: Optional[str] = SQLField(default=None, sa_type=String, validation_alias="FACEUNIT")
    latname: Optional[str] = SQLField(default=None, sa_type=Text, validation_alias="LATNAME")
    startdatemoex: Optional[date] = SQLField(
        default=None, sa_type=Date, validation_alias="STARTDATEMOEX"
    )
    hasprospectus: Optional[bool] = SQLField(
        default=None, sa_type=Boolean, validation_alias="HASPROSPECTUS"
    )
    decisiondate: Optional[date] = SQLField(
        default=None, sa_type=Date, validation_alias="DECISIONDATE"
    )
    isconcessionagreement: Optional[bool] = SQLField(
        default=None, sa_type=Boolean, validation_alias="ISCONCESSIONAGREEMENT"
    )
    hasdefault: Optional[bool] = SQLField(default=None, sa_type=Boolean, validation_alias="HASDEFAULT")
    hastechnicaldefault: Optional[bool] = SQLField(
        default=None, sa_type=Boolean, validation_alias="HASTECHNICALDEFAULT"
    )
    programregistrynumber: Optional[str] = SQLField(
        default=None, sa_type=String, validation_alias="PROGRAMREGISTRYNUMBER"
    )
    emitentmismatchcur: Optional[int] = SQLField(
        default=None, sa_type=Integer, validation_alias="EMITENTMISMATCHCUR"
    )
    daystoredemption: Optional[int] = SQLField(
        default=None, sa_type=Integer, validation_alias="DAYSTOREDEMPTION"
    )
    issuesize: Optional[int] = SQLField(default=None, sa_type=BigInteger, validation_alias="ISSUESIZE")
    facevalue: Optional[Decimal] = SQLField(
        default=None, sa_type=Numeric(15, 2), validation_alias="FACEVALUE"
    )
    isqualifiedinvestors: Optional[bool] = SQLField(
        default=None, sa_type=Boolean, validation_alias="ISQUALIFIEDINVESTORS"
    )
    coupon_benchmark: Optional[str] = SQLField(
        default=None, sa_type=String, validation_alias="COUPON_BENCHMARK"
    )
    coupon_benchmark_spread: Optional[Decimal] = SQLField(
        default=None, sa_type=Numeric(10, 4), validation_alias="COUPON_BENCHMARK_SPREAD"
    )
    morningsession: Optional[bool] = SQLField(
        default=None, sa_type=Boolean, validation_alias="MORNINGSESSION"
    )
    eveningsession: Optional[bool] = SQLField(
        default=None, sa_type=Boolean, validation_alias="EVENINGSESSION"
    )
    weekendsession: Optional[bool] = SQLField(
        default=None, sa_type=Boolean, validation_alias="WEEKENDSESSION"
    )
    registry_date: Optional[date] = SQLField(
        default=None, sa_type=Date, validation_alias="REGISTRY_DATE"
    )
    bond_type: Optional[str] = SQLField(default=None, sa_type=String, validation_alias="BOND_TYPE")
    bond_subtype: Optional[str] = SQLField(
        default=None, sa_type=String, validation_alias="BOND_SUBTYPE"
    )
    facevalue_type: Optional[str] = SQLField(
        default=None, sa_type=String, validation_alias="FACEVALUE_TYPE"
    )
    coupon_details: Optional[str] = SQLField(
        default=None, sa_type=String, validation_alias="COUPON_DETAILS"
    )
    typename: Optional[str] = SQLField(default=None, sa_type=String, validation_alias="TYPENAME")
    group: Optional[str] = SQLField(default=None, sa_type=String, validation_alias="GROUP")
    type: Optional[str] = SQLField(default=None, sa_type=String, validation_alias="TYPE")
    groupname: Optional[str] = SQLField(default=None, sa_type=String, validation_alias="GROUPNAME")
    emitter_id: Optional[int] = SQLField(
        default=None,
        sa_type=Integer,
        foreign_key="emitents.moex_id",
        ondelete="SET NULL",
        validation_alias="EMITTER_ID",
    )

    @field_validator("*", mode="before")
    @classmethod
    def empty_strings_are_null(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


class BondDescription(BondDescriptionBase, table=True):
    """MOEX description row, keyed by the related ``bonds.id``."""

    __tablename__ = "bond_description"
