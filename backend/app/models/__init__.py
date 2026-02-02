"""Модели данных для приложения BondsScreener.

Этот пакет содержит все модели данных (Pydantic), используемые в приложении
для валидации и сериализации данных облигаций, купонов, эмитентов и фильтров.

Модули:
    bond: Модели данных облигаций (Bond — SQLModel таблица bonds; BondListItem, BondDetail, BondSecurity, BondMarketData)
    currencyrate: SQLModel таблица currencyrate (DBcurrencyrate) — курсы валют ЦБ РФ
    keyrate: SQLModel таблица keyrate (DBkeyrate) — данные ключевой ставки ЦБ РФ
    keyrate_dto: DTO для API ключевой ставки (KeyrateDTO)
    ruonia: SQLModel таблица ruonia (DBruonia) — данные индикатора RUONIA ЦБ РФ
    ruonia_dto: DTO для API RUONIA (RuoniaDTO, RuoniaDataResponse)
    bonds_dto: DTO для API скринера облигаций (BondScreenerDTO)
    kbd_DTO: DTO для кривой бескупонной доходности (KbdDTO, KbdDataResponse)
    kbd_model: SQLModel таблица kbd (DBkbd)
    coupons: Модели данных купонов (Coupon, Offer)
    emitent: Модели данных эмитентов (EmitentInfo)
    filters: Модели фильтров для поиска облигаций (BondFilters)
    responses: Модели ответов API (BondsListResponse, ErrorResponse и др.)
"""
