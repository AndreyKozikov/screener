"""Baseline current main schema

Revision ID: 025_baseline_current_schema
Revises:
Create Date: 2026-11-08

Baseline текущей схемы. Создан по фактическому состоянию базы.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "025_baseline_current_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE rating_agency (
	id INTEGER NOT NULL, 
	agency_id INTEGER NOT NULL, 
	agency_name_short_ru VARCHAR(64) NOT NULL, 
	agency_name_full_ru VARCHAR(256), 
	is_system INTEGER DEFAULT '0' NOT NULL, 
	PRIMARY KEY (id)
)"""
    )
    op.execute(
        """CREATE TABLE ruonia (
	dt DATE NOT NULL, 
	ruo FLOAT, 
	vol FLOAT, 
	"T" FLOAT, 
	"C" FLOAT, 
	"MinRate" FLOAT, 
	"Percentile25" FLOAT, 
	"Percentile75" FLOAT, 
	"MaxRate" FLOAT, 
	"StatusXML" FLOAT, 
	"DateUpdate" VARCHAR(64), 
	PRIMARY KEY (dt)
)"""
    )
    op.execute(
        """CREATE TABLE "keyrate" (
	"dt"	DATE NOT NULL,
	"rate"	FLOAT NOT NULL DEFAULT '0',
	PRIMARY KEY("dt")
)"""
    )
    op.execute(
        """CREATE TABLE currencyrate (
	dt DATE NOT NULL, 
	source_date VARCHAR(32) DEFAULT '' NOT NULL, 
	usd_rate FLOAT, 
	usd_nominal INTEGER, 
	usd_original_value VARCHAR(32), 
	eur_rate FLOAT, 
	eur_nominal INTEGER, 
	eur_original_value VARCHAR(32), 
	cny_rate FLOAT, 
	cny_nominal INTEGER, 
	cny_original_value VARCHAR(32), 
	PRIMARY KEY (dt)
)"""
    )
    op.execute(
        """CREATE TABLE emitents (
	id INTEGER NOT NULL, 
	moex_id INTEGER, 
	inn VARCHAR(32), 
	okpo VARCHAR(32), 
	title VARCHAR, type VARCHAR(64), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_emitents_moex_id UNIQUE (moex_id), 
	CONSTRAINT uq_emitents_inn UNIQUE (inn)
)"""
    )
    op.execute(
        """CREATE TABLE "bonds" (
	id INTEGER NOT NULL, 
	secid VARCHAR(64) NOT NULL, 
	boardid VARCHAR(32), 
	isin VARCHAR(32), 
	name VARCHAR, 
	secname VARCHAR, 
	rating VARCHAR(32), 
	rating_agency VARCHAR(64), 
	current_price FLOAT, 
	coupon_yield_to_price FLOAT, 
	yield_to_maturity FLOAT, 
	face_value FLOAT, 
	currency VARCHAR(16), 
	face_unit VARCHAR(16), 
	coupon_value FLOAT, 
	coupon_percent FLOAT, 
	coupon_frequency FLOAT, 
	coupon_period INTEGER, 
	accrued_interest FLOAT, 
	duration_years FLOAT, 
	duration FLOAT, 
	duration_waprice INTEGER, 
	has_put_option INTEGER, 
	has_call_option INTEGER, 
	maturity_date VARCHAR(10), 
	listing_level INTEGER, 
	bond_type INTEGER, 
	bond_kind INTEGER, 
	offer_date VARCHAR(10), 
	status VARCHAR(32), 
	trading_status VARCHAR(32), 
	next_coupon VARCHAR(10), 
	board_name VARCHAR(128), 
	call_option_date VARCHAR(10), 
	put_option_date VARCHAR(10), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_bonds_secid_boardid UNIQUE (secid, boardid)
)"""
    )
    op.execute(
        """CREATE TABLE "bond_emitents" (
	secid VARCHAR(64) NOT NULL, 
	emitent_id INTEGER NOT NULL, 
	PRIMARY KEY (secid), 
	FOREIGN KEY(emitent_id) REFERENCES emitents (id) ON DELETE CASCADE
)"""
    )
    op.execute(
        """CREATE TABLE bond_float_params (
	id INTEGER NOT NULL, 
	bond_id INTEGER NOT NULL, 
	base_indicator_code VARCHAR(64) NOT NULL, 
	spread FLOAT, 
	coupon_frequency_days INTEGER, 
	lookback_period INTEGER, 
	averaging_period INTEGER, 
	formula_raw TEXT, 
	rate_determination_rule TEXT, 
	calculation_type VARCHAR(32), 
	rounding_precision INTEGER, 
	key_rate_method VARCHAR(32), 
	lookback_type VARCHAR(32), 
	year_base VARCHAR(16), 
	is_daily_accrual BOOLEAN DEFAULT '0' NOT NULL, 
	offset_days INTEGER, 
	offset_calendar VARCHAR(32), 
	day_count VARCHAR(32), 
	fallback VARCHAR(32), 
	accrual_type VARCHAR(32), 
	interest_compounding BOOLEAN DEFAULT '0' NOT NULL, 
	placement_date VARCHAR(10), 
	underwriter TEXT, is_find INTEGER DEFAULT '1' NOT NULL, floor_rate FLOAT, cap_rate FLOAT, extra_indicators TEXT, condition_logic TEXT, observation_type VARCHAR(64), reference_period_desc TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(bond_id) REFERENCES bonds (id) ON DELETE CASCADE
)"""
    )
    op.execute(
        """CREATE TABLE bond_ratings (
	id INTEGER NOT NULL, 
	bond_id INTEGER NOT NULL, 
	agency_id INTEGER NOT NULL, 
	rating_level_name TEXT NOT NULL, 
	rating_date TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(bond_id) REFERENCES bonds (id) ON DELETE CASCADE, 
	FOREIGN KEY(agency_id) REFERENCES rating_agency (agency_id)
)"""
    )
    op.execute(
        """CREATE TABLE bondmarketdata (
	id INTEGER NOT NULL, 
	bond_id INTEGER, 
	boardid VARCHAR(32), 
	bid FLOAT, 
	offer FLOAT, 
	spread FLOAT, 
	bid_depth INTEGER, 
	offer_depth INTEGER, 
	open_price FLOAT, 
	low FLOAT, 
	high FLOAT, 
	last_price FLOAT, 
	last_change FLOAT, 
	last_change_prcnt FLOAT, 
	qty INTEGER, 
	value FLOAT, 
	value_usd FLOAT, 
	waprice FLOAT, 
	last_cnt_to_last_waprice FLOAT, 
	wap_to_prev_waprice_prcnt FLOAT, 
	wap_to_prev_waprice FLOAT, 
	close_price FLOAT, 
	market_price_today FLOAT, 
	market_price FLOAT, 
	last_to_prev_price FLOAT, 
	num_trades INTEGER, 
	vol_today INTEGER, 
	val_today FLOAT, 
	val_today_usd FLOAT, 
	etf_settle_price FLOAT, 
	update_time VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(bond_id) REFERENCES bonds (id)
)"""
    )
    op.execute(
        """CREATE TABLE bondmarketdatayield (
	id INTEGER NOT NULL, 
	bond_id INTEGER, 
	boardid VARCHAR(32), 
	price FLOAT, 
	yield_date VARCHAR(10), 
	zcyc_moment VARCHAR(32), 
	yield_date_type VARCHAR(32), 
	effective_yield FLOAT, 
	duration INTEGER, 
	zspread_bp INTEGER, 
	gspread_bp INTEGER, 
	waprice FLOAT, 
	effective_yield_waprice FLOAT, 
	duration_waprice INTEGER, 
	ir FLOAT, 
	icpi FLOAT, 
	bei FLOAT, 
	cbr FLOAT, 
	yield_to_offer FLOAT, 
	yield_last_coupon FLOAT, 
	trade_moment VARCHAR(32), 
	seqnum INTEGER, 
	systime VARCHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(bond_id) REFERENCES bonds (id)
)"""
    )
    op.execute(
        """CREATE TABLE bondsecurity (
	id INTEGER NOT NULL, 
	bond_id INTEGER, 
	boardid VARCHAR(32), 
	prev_waprice FLOAT, 
	yield_at_prev_waprice FLOAT, 
	prev_price FLOAT, 
	lot_size INTEGER, 
	reg_number VARCHAR, 
	decimals INTEGER, 
	issue_size INTEGER, 
	prev_legal_close_price FLOAT, 
	prev_date DATE, 
	remarks VARCHAR, 
	market_code VARCHAR, 
	instr_id VARCHAR, 
	sector_id VARCHAR, 
	min_step FLOAT, 
	face_unit VARCHAR, 
	buyback_price FLOAT, 
	buyback_date DATE, 
	lat_name VARCHAR, 
	issue_size_placed INTEGER, 
	sec_type VARCHAR, 
	settle_date DATE, 
	lot_value FLOAT, 
	face_value_on_settle_date FLOAT, 
	date_yield_from_issuer DATE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(bond_id) REFERENCES bonds (id)
)"""
    )
    op.execute(
        """CREATE TABLE "coupons" (
	bond_id INTEGER NOT NULL, 
	coupondate DATE, 
	recorddate DATE, 
	startdate DATE, 
	initialfacevalue INTEGER, 
	facevalue INTEGER, 
	faceunit TEXT, 
	value REAL, 
	valueprc REAL, 
	value_rub REAL, 
	CONSTRAINT pk_coupons_new PRIMARY KEY (bond_id, coupondate), 
	FOREIGN KEY(bond_id) REFERENCES bonds (id) ON DELETE CASCADE
)"""
    )
    op.execute(
        """CREATE TABLE describe_fields (
	id INTEGER NOT NULL, 
	section VARCHAR(32) NOT NULL, 
	field_name VARCHAR(128) NOT NULL, 
	description TEXT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_describe_fields_section_field UNIQUE (section, field_name)
)"""
    )
    op.execute(
        """CREATE TABLE emitent_edisclosure (
	id INTEGER NOT NULL, 
	emitent_id INTEGER NOT NULL, 
	edisclosure_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (emitent_id), 
	FOREIGN KEY(emitent_id) REFERENCES emitents (id)
)"""
    )
    op.execute(
        """CREATE TABLE "emission_documents" (
	id INTEGER NOT NULL, 
	emitent_edisclosure_id INTEGER NOT NULL, 
	doc_type TEXT NOT NULL, 
	reg_number TEXT, 
	date_registration TEXT, 
	registering_org TEXT, 
	date_ground_publication TEXT, 
	date_placement TEXT, 
	file_url TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(emitent_edisclosure_id) REFERENCES emitent_edisclosure (id)
)"""
    )
    op.execute(
        """CREATE TABLE "emitent_ratings" (
	id INTEGER NOT NULL, 
	emitent_id INTEGER NOT NULL, 
	agency_id INTEGER NOT NULL, 
	rating_level_name TEXT, 
	rating_date DATETIME, 
	rating_publicate_date DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_emitent_ratings_emitent_agency UNIQUE (emitent_id, agency_id), 
	FOREIGN KEY(emitent_id) REFERENCES emitents (id) ON DELETE CASCADE, 
	FOREIGN KEY(agency_id) REFERENCES rating_agency (id) ON DELETE CASCADE
)"""
    )
    op.execute(
        """CREATE TABLE events_details (
	id INTEGER NOT NULL, 
	pseudo_guid VARCHAR NOT NULL, 
	event_date DATE NOT NULL, 
	registration_number VARCHAR, 
	issue_registration_number VARCHAR, 
	isin VARCHAR, 
	series VARCHAR, 
	security_type VARCHAR, 
	message_type VARCHAR, 
	event_type VARCHAR, 
	publication_date VARCHAR, emitent_inn VARCHAR, is_edit INTEGER DEFAULT '0' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_events_details_guid_date UNIQUE (pseudo_guid, event_date)
)"""
    )
    op.execute(
        """CREATE TABLE forecast (
	date DATE NOT NULL, 
	meeting_date DATE NOT NULL, 
	publication_date DATE NOT NULL, 
	PRIMARY KEY (date)
)"""
    )
    op.execute(
        """CREATE TABLE forecast_balance (
	forecast_date DATE NOT NULL, 
	year INTEGER NOT NULL, 
	account_current_operations FLOAT, 
	trade_balance FLOAT, 
	goods_export FLOAT, 
	goods_import FLOAT, 
	services_balance FLOAT, 
	services_export FLOAT, 
	services_import FLOAT, 
	income_balance FLOAT, 
	financial_account FLOAT, 
	liabilities_net FLOAT, 
	assets_net FLOAT, 
	errors_omissions FLOAT, 
	reserves_change FLOAT, 
	oil_price FLOAT, 
	PRIMARY KEY (forecast_date, year), 
	FOREIGN KEY(forecast_date) REFERENCES forecast (date) ON DELETE CASCADE
)"""
    )
    op.execute(
        """CREATE TABLE forecast_indicator_name (
	section VARCHAR(32) NOT NULL, 
	"key" VARCHAR(64) NOT NULL, 
	title TEXT NOT NULL, 
	PRIMARY KEY (section, "key")
)"""
    )
    op.execute(
        """CREATE TABLE forecast_main_indicators (
	forecast_date DATE NOT NULL, 
	year INTEGER NOT NULL, 
	inflation_dec_min FLOAT, 
	inflation_dec_max FLOAT, 
	inflation_avg_min FLOAT, 
	inflation_avg_max FLOAT, 
	key_rate_min FLOAT, 
	key_rate_max FLOAT, 
	gdp_min FLOAT, 
	gdp_max FLOAT, 
	gdp_q4_min FLOAT, 
	gdp_q4_max FLOAT, 
	consumption_min FLOAT, 
	consumption_max FLOAT, 
	household_consumption_min FLOAT, 
	household_consumption_max FLOAT, 
	accumulation_min FLOAT, 
	accumulation_max FLOAT, 
	capital_accumulation_min FLOAT, 
	capital_accumulation_max FLOAT, 
	export_min FLOAT, 
	export_max FLOAT, 
	import_min FLOAT, 
	import_max FLOAT, 
	money_supply_min FLOAT, 
	money_supply_max FLOAT, 
	claims_economy_min FLOAT, 
	claims_economy_max FLOAT, 
	claims_orgs_min FLOAT, 
	claims_orgs_max FLOAT, 
	claims_households_min FLOAT, 
	claims_households_max FLOAT, 
	mortgage_loans_min FLOAT, 
	mortgage_loans_max FLOAT, 
	PRIMARY KEY (forecast_date, year), 
	FOREIGN KEY(forecast_date) REFERENCES forecast (date) ON DELETE CASCADE
)"""
    )
    op.execute(
        """CREATE TABLE inflation_data (
	record_date DATE NOT NULL, 
	trend_inflation_3y FLOAT, 
	trend_inflation_5y FLOAT, 
	modified_core_inflation FLOAT, 
	PRIMARY KEY (record_date)
)"""
    )
    op.execute(
        """CREATE TABLE inflation_expectations (
	recorddata DATE NOT NULL, 
	observed_annual_inflation FLOAT, 
	expected_annual_inflation FLOAT, 
	expected_five_year_inflation FLOAT, 
	expectations_index FLOAT, 
	PRIMARY KEY (recorddata)
)"""
    )
    op.execute(
        """CREATE TABLE ipc_table (
	record_data DATE NOT NULL, 
	ipc FLOAT, 
	food_ipc FLOAT, 
	non_food_ipc FLOAT, 
	services_ipc FLOAT, 
	PRIMARY KEY (record_data)
)"""
    )
    op.execute(
        """CREATE TABLE ipc_weekly (
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	ipc_weekly FLOAT, 
	source_url VARCHAR, 
	PRIMARY KEY (start_date)
)"""
    )
    op.execute(
        """CREATE TABLE kbd (
            date DATE NOT NULL,
            time TIME NOT NULL,
            term_0_25 REAL,
            term_0_5 REAL,
            term_0_75 REAL,
            term_1_0 REAL,
            term_2_0 REAL,
            term_3_0 REAL,
            term_5_0 REAL,
            term_7_0 REAL,
            term_10_0 REAL,
            term_15_0 REAL,
            term_20_0 REAL,
            term_30_0 REAL,
            PRIMARY KEY (date, time)
        )"""
    )
    op.execute(
        """CREATE TABLE users (id VARCHAR(36) NOT NULL PRIMARY KEY, email VARCHAR(320) NOT NULL, password_hash VARCHAR(512) NOT NULL, created_at VARCHAR NOT NULL, updated_at VARCHAR NOT NULL)"""
    )
    op.execute(
        """CREATE INDEX idx_bond_ratings_bond_id ON bond_ratings (bond_id)"""
    )
    op.execute(
        """CREATE INDEX idx_coupons_bond_id ON coupons (bond_id)"""
    )
    op.execute(
        """CREATE INDEX idx_emitent_ratings_agency_id ON emitent_ratings (agency_id)"""
    )
    op.execute(
        """CREATE INDEX idx_emitent_ratings_emitent_id ON emitent_ratings (emitent_id)"""
    )
    op.execute(
        """CREATE UNIQUE INDEX idx_rating_agency_agency_id ON rating_agency (agency_id)"""
    )
    op.execute(
        """CREATE INDEX idx_rating_agency_name ON rating_agency (agency_name_short_ru)"""
    )
    op.execute(
        """CREATE INDEX ix_describe_fields_field_name ON describe_fields (field_name)"""
    )
    op.execute(
        """CREATE INDEX ix_describe_fields_section ON describe_fields (section)"""
    )
    op.execute(
        """CREATE INDEX ix_emission_documents_emitent_edisclosure_id ON emission_documents (emitent_edisclosure_id)"""
    )
    op.execute(
        """CREATE INDEX ix_events_details_emitent_inn ON events_details (emitent_inn)"""
    )
    op.execute(
        """CREATE INDEX ix_events_details_event_date ON events_details (event_date)"""
    )
    op.execute(
        """CREATE INDEX ix_events_details_pseudo_guid ON events_details (pseudo_guid)"""
    )
    op.execute(
        """CREATE UNIQUE INDEX uq_bond_float_params_bond_id ON bond_float_params (bond_id)"""
    )
    op.execute(
        """CREATE UNIQUE INDEX uq_bond_rating_date ON bond_ratings (bond_id, agency_id, rating_date)"""
    )
    op.execute(
        """CREATE UNIQUE INDEX uq_bondmarketdata_bond_id ON bondmarketdata (bond_id)"""
    )
    op.execute(
        """CREATE UNIQUE INDEX uq_bondmarketdatayield_bond_id ON bondmarketdatayield (bond_id)"""
    )
    op.execute(
        """CREATE UNIQUE INDEX uq_bondsecurity_bond_id ON bondsecurity (bond_id)"""
    )
    op.execute(
        """CREATE UNIQUE INDEX uq_users_email ON users (email)"""
    )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS "uq_users_email"')
    op.execute('DROP INDEX IF EXISTS "uq_bondsecurity_bond_id"')
    op.execute('DROP INDEX IF EXISTS "uq_bondmarketdatayield_bond_id"')
    op.execute('DROP INDEX IF EXISTS "uq_bondmarketdata_bond_id"')
    op.execute('DROP INDEX IF EXISTS "uq_bond_rating_date"')
    op.execute('DROP INDEX IF EXISTS "uq_bond_float_params_bond_id"')
    op.execute('DROP INDEX IF EXISTS "ix_events_details_pseudo_guid"')
    op.execute('DROP INDEX IF EXISTS "ix_events_details_event_date"')
    op.execute('DROP INDEX IF EXISTS "ix_events_details_emitent_inn"')
    op.execute('DROP INDEX IF EXISTS "ix_emission_documents_emitent_edisclosure_id"')
    op.execute('DROP INDEX IF EXISTS "ix_describe_fields_section"')
    op.execute('DROP INDEX IF EXISTS "ix_describe_fields_field_name"')
    op.execute('DROP INDEX IF EXISTS "idx_rating_agency_name"')
    op.execute('DROP INDEX IF EXISTS "idx_rating_agency_agency_id"')
    op.execute('DROP INDEX IF EXISTS "idx_emitent_ratings_emitent_id"')
    op.execute('DROP INDEX IF EXISTS "idx_emitent_ratings_agency_id"')
    op.execute('DROP INDEX IF EXISTS "idx_coupons_bond_id"')
    op.execute('DROP INDEX IF EXISTS "idx_bond_ratings_bond_id"')
    op.execute('DROP TABLE IF EXISTS "users"')
    op.execute('DROP TABLE IF EXISTS "kbd"')
    op.execute('DROP TABLE IF EXISTS "ipc_weekly"')
    op.execute('DROP TABLE IF EXISTS "ipc_table"')
    op.execute('DROP TABLE IF EXISTS "inflation_expectations"')
    op.execute('DROP TABLE IF EXISTS "inflation_data"')
    op.execute('DROP TABLE IF EXISTS "forecast_main_indicators"')
    op.execute('DROP TABLE IF EXISTS "forecast_indicator_name"')
    op.execute('DROP TABLE IF EXISTS "forecast_balance"')
    op.execute('DROP TABLE IF EXISTS "forecast"')
    op.execute('DROP TABLE IF EXISTS "events_details"')
    op.execute('DROP TABLE IF EXISTS "emitent_ratings"')
    op.execute('DROP TABLE IF EXISTS "emission_documents"')
    op.execute('DROP TABLE IF EXISTS "emitent_edisclosure"')
    op.execute('DROP TABLE IF EXISTS "describe_fields"')
    op.execute('DROP TABLE IF EXISTS "coupons"')
    op.execute('DROP TABLE IF EXISTS "bondsecurity"')
    op.execute('DROP TABLE IF EXISTS "bondmarketdatayield"')
    op.execute('DROP TABLE IF EXISTS "bondmarketdata"')
    op.execute('DROP TABLE IF EXISTS "bond_ratings"')
    op.execute('DROP TABLE IF EXISTS "bond_float_params"')
    op.execute('DROP TABLE IF EXISTS "bond_emitents"')
    op.execute('DROP TABLE IF EXISTS "bonds"')
    op.execute('DROP TABLE IF EXISTS "emitents"')
    op.execute('DROP TABLE IF EXISTS "currencyrate"')
    op.execute('DROP TABLE IF EXISTS "keyrate"')
    op.execute('DROP TABLE IF EXISTS "ruonia"')
    op.execute('DROP TABLE IF EXISTS "rating_agency"')
