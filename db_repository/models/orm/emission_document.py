"""ORM-модель таблицы эмиссионных документов (SQLModel)."""

from typing import Optional

from sqlmodel import SQLModel, Field as SQLField


class EmissionDocument(SQLModel, table=True):
    """Эмиссионный документ эмитента с e-disclosure.ru.

    Attributes:
        id: Первичный ключ (autoincrement).
        emitent_edisclosure_id: FK на emitent_edisclosure.id.
        doc_type: Тип документа.
        reg_number: Регистрационный номер.
        date_registration: Дата регистрации (дата уведомления).
        registering_org: Регистрирующий орган (организация).
        date_ground_publication: Дата наступления основания для опубликования.
        date_placement: Дата размещения.
        file_url: Прямая ссылка на скачивание файла.
    """

    __tablename__ = "emission_documents"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    emitent_edisclosure_id: int = SQLField(
        foreign_key="emitent_edisclosure.id", nullable=False, index=True
    )
    doc_type: str = SQLField(nullable=False)
    reg_number: Optional[str] = SQLField(default=None, nullable=True)
    date_registration: Optional[str] = SQLField(default=None, nullable=True)
    registering_org: Optional[str] = SQLField(default=None, nullable=True)
    date_ground_publication: Optional[str] = SQLField(default=None, nullable=True)
    date_placement: Optional[str] = SQLField(default=None, nullable=True)
    file_url: Optional[str] = SQLField(default=None, nullable=True)
