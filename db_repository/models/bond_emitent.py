from sqlmodel import SQLModel, Field as SQLField


class BondEmitent(SQLModel, table=True):
    __tablename__ = "bond_emitents"

    secid: str = SQLField(
        primary_key=True,
        max_length=64,
    )

    emitent_id: int = SQLField(
        foreign_key="emitents.id",
        ondelete="CASCADE"
    )