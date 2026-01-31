"""Модели данных для приложения BondsScreener.

Этот пакет содержит все модели данных (Pydantic), используемые в приложении
для валидации и сериализации данных облигаций, купонов, эмитентов и фильтров.

Модули:
    bond: Модели данных облигаций (Bond — SQLModel таблица bonds; BondListItem, BondDetail, BondSecurity, BondMarketData)
    coupons: Модели данных купонов (Coupon, Offer)
    emitent: Модели данных эмитентов (EmitentInfo)
    filters: Модели фильтров для поиска облигаций (BondFilters)
    responses: Модели ответов API (BondsListResponse, ErrorResponse и др.)
"""
