"""bonds_pipeline_restructure_id_pk

Revision ID: d33e65bc9db2
Revises: 005
Create Date: 2026-02-03 21:36:28.810024

Изменения:
- bonds: добавлен id как PRIMARY KEY AUTOINCREMENT, secid больше не PK, удалён ratings
- bondsecurity, bondmarketdata, bondmarketdatayield: добавлен id как PK, secid заменён на bond_id (FK)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd33e65bc9db2'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite не поддерживает ALTER TABLE для изменения PK, поэтому пересоздаём таблицы
    # Данные в этих таблицах полностью перезаписываются при каждом refresh
    
    # 1. Удаляем связанные таблицы (они зависят от bonds)
    op.drop_table('bondmarketdatayield')
    op.drop_table('bondmarketdata')
    op.drop_table('bondsecurity')
    
    # 2. Удаляем таблицу bonds
    op.drop_table('bonds')
    
    # 3. Создаём новую таблицу bonds с id как PK
    op.create_table(
        'bonds',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('secid', sa.String(length=64), nullable=False),
        sa.Column('boardid', sa.String(length=32), nullable=True),
        sa.Column('isin', sa.String(length=32), nullable=True),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('secname', sa.String(), nullable=True),
        sa.Column('rating', sa.String(length=32), nullable=True),
        sa.Column('rating_agency', sa.String(length=64), nullable=True),
        sa.Column('current_price', sa.Float(), nullable=True),
        sa.Column('coupon_yield_to_price', sa.Float(), nullable=True),
        sa.Column('yield_to_maturity', sa.Float(), nullable=True),
        sa.Column('face_value', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(length=16), nullable=True),
        sa.Column('face_unit', sa.String(length=16), nullable=True),
        sa.Column('coupon_value', sa.Float(), nullable=True),
        sa.Column('coupon_percent', sa.Float(), nullable=True),
        sa.Column('coupon_frequency', sa.Float(), nullable=True),
        sa.Column('coupon_period', sa.Integer(), nullable=True),
        sa.Column('accrued_interest', sa.Float(), nullable=True),
        sa.Column('duration_years', sa.Float(), nullable=True),
        sa.Column('duration', sa.Float(), nullable=True),
        sa.Column('duration_waprice', sa.Integer(), nullable=True),
        sa.Column('has_put_option', sa.Integer(), nullable=True),
        sa.Column('has_call_option', sa.Integer(), nullable=True),
        sa.Column('maturity_date', sa.String(length=10), nullable=True),
        sa.Column('listing_level', sa.Integer(), nullable=True),
        sa.Column('bond_type', sa.Integer(), nullable=True),
        sa.Column('bond_kind', sa.Integer(), nullable=True),
        sa.Column('offer_date', sa.String(length=10), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=True),
        sa.Column('trading_status', sa.String(length=32), nullable=True),
        sa.Column('next_coupon', sa.String(length=10), nullable=True),
        sa.Column('board_name', sa.String(length=128), nullable=True),
        sa.Column('call_option_date', sa.String(length=10), nullable=True),
        sa.Column('put_option_date', sa.String(length=10), nullable=True),
    )
    
    # 4. Создаём таблицу bondsecurity с id и bond_id
    op.create_table(
        'bondsecurity',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('bond_id', sa.Integer(), sa.ForeignKey('bonds.id'), nullable=True),
        sa.Column('boardid', sa.String(length=32), nullable=True),
        sa.Column('prev_waprice', sa.Float(), nullable=True),
        sa.Column('yield_at_prev_waprice', sa.Float(), nullable=True),
        sa.Column('prev_price', sa.Float(), nullable=True),
        sa.Column('lot_size', sa.Integer(), nullable=True),
        sa.Column('reg_number', sa.String(), nullable=True),
        sa.Column('decimals', sa.Integer(), nullable=True),
        sa.Column('issue_size', sa.Integer(), nullable=True),
        sa.Column('prev_legal_close_price', sa.Float(), nullable=True),
        sa.Column('prev_date', sa.Date(), nullable=True),
        sa.Column('remarks', sa.String(), nullable=True),
        sa.Column('market_code', sa.String(), nullable=True),
        sa.Column('instr_id', sa.String(), nullable=True),
        sa.Column('sector_id', sa.String(), nullable=True),
        sa.Column('min_step', sa.Float(), nullable=True),
        sa.Column('face_unit', sa.String(), nullable=True),
        sa.Column('buyback_price', sa.Float(), nullable=True),
        sa.Column('buyback_date', sa.Date(), nullable=True),
        sa.Column('lat_name', sa.String(), nullable=True),
        sa.Column('issue_size_placed', sa.Integer(), nullable=True),
        sa.Column('sec_type', sa.String(), nullable=True),
        sa.Column('settle_date', sa.Date(), nullable=True),
        sa.Column('lot_value', sa.Float(), nullable=True),
        sa.Column('face_value_on_settle_date', sa.Float(), nullable=True),
        sa.Column('date_yield_from_issuer', sa.Date(), nullable=True),
    )
    
    # 5. Создаём таблицу bondmarketdata с id и bond_id
    op.create_table(
        'bondmarketdata',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('bond_id', sa.Integer(), sa.ForeignKey('bonds.id'), nullable=True),
        sa.Column('boardid', sa.String(length=32), nullable=True),
        sa.Column('bid', sa.Float(), nullable=True),
        sa.Column('offer', sa.Float(), nullable=True),
        sa.Column('spread', sa.Float(), nullable=True),
        sa.Column('bid_depth', sa.Integer(), nullable=True),
        sa.Column('offer_depth', sa.Integer(), nullable=True),
        sa.Column('open_price', sa.Float(), nullable=True),
        sa.Column('low', sa.Float(), nullable=True),
        sa.Column('high', sa.Float(), nullable=True),
        sa.Column('last_price', sa.Float(), nullable=True),
        sa.Column('last_change', sa.Float(), nullable=True),
        sa.Column('last_change_prcnt', sa.Float(), nullable=True),
        sa.Column('qty', sa.Integer(), nullable=True),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('value_usd', sa.Float(), nullable=True),
        sa.Column('waprice', sa.Float(), nullable=True),
        sa.Column('last_cnt_to_last_waprice', sa.Float(), nullable=True),
        sa.Column('wap_to_prev_waprice_prcnt', sa.Float(), nullable=True),
        sa.Column('wap_to_prev_waprice', sa.Float(), nullable=True),
        sa.Column('close_price', sa.Float(), nullable=True),
        sa.Column('market_price_today', sa.Float(), nullable=True),
        sa.Column('market_price', sa.Float(), nullable=True),
        sa.Column('last_to_prev_price', sa.Float(), nullable=True),
        sa.Column('num_trades', sa.Integer(), nullable=True),
        sa.Column('vol_today', sa.Integer(), nullable=True),
        sa.Column('val_today', sa.Float(), nullable=True),
        sa.Column('val_today_usd', sa.Float(), nullable=True),
        sa.Column('etf_settle_price', sa.Float(), nullable=True),
        sa.Column('update_time', sa.String(), nullable=True),
    )
    
    # 6. Создаём таблицу bondmarketdatayield с id и bond_id
    op.create_table(
        'bondmarketdatayield',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('bond_id', sa.Integer(), sa.ForeignKey('bonds.id'), nullable=True),
        sa.Column('boardid', sa.String(length=32), nullable=True),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('yield_date', sa.String(length=10), nullable=True),
        sa.Column('zcyc_moment', sa.String(length=32), nullable=True),
        sa.Column('yield_date_type', sa.String(length=32), nullable=True),
        sa.Column('effective_yield', sa.Float(), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('zspread_bp', sa.Integer(), nullable=True),
        sa.Column('gspread_bp', sa.Integer(), nullable=True),
        sa.Column('waprice', sa.Float(), nullable=True),
        sa.Column('effective_yield_waprice', sa.Float(), nullable=True),
        sa.Column('duration_waprice', sa.Integer(), nullable=True),
        sa.Column('ir', sa.Float(), nullable=True),
        sa.Column('icpi', sa.Float(), nullable=True),
        sa.Column('bei', sa.Float(), nullable=True),
        sa.Column('cbr', sa.Float(), nullable=True),
        sa.Column('yield_to_offer', sa.Float(), nullable=True),
        sa.Column('yield_last_coupon', sa.Float(), nullable=True),
        sa.Column('trade_moment', sa.String(length=32), nullable=True),
        sa.Column('seqnum', sa.Integer(), nullable=True),
        sa.Column('systime', sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    # Удаляем новые таблицы
    op.drop_table('bondmarketdatayield')
    op.drop_table('bondmarketdata')
    op.drop_table('bondsecurity')
    op.drop_table('bonds')
    
    # Восстанавливаем старые таблицы со старой структурой
    op.create_table(
        'bonds',
        sa.Column('secid', sa.String(length=64), primary_key=True),
        sa.Column('boardid', sa.String(length=32), nullable=True),
        sa.Column('isin', sa.String(length=32), nullable=True),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('secname', sa.String(), nullable=True),
        sa.Column('rating', sa.String(length=32), nullable=True),
        sa.Column('rating_agency', sa.String(length=64), nullable=True),
        sa.Column('current_price', sa.Float(), nullable=True),
        sa.Column('coupon_yield_to_price', sa.Float(), nullable=True),
        sa.Column('yield_to_maturity', sa.Float(), nullable=True),
        sa.Column('face_value', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(length=16), nullable=True),
        sa.Column('face_unit', sa.String(length=16), nullable=True),
        sa.Column('coupon_value', sa.Float(), nullable=True),
        sa.Column('coupon_percent', sa.Float(), nullable=True),
        sa.Column('coupon_frequency', sa.Float(), nullable=True),
        sa.Column('coupon_period', sa.Integer(), nullable=True),
        sa.Column('accrued_interest', sa.Float(), nullable=True),
        sa.Column('duration_years', sa.Float(), nullable=True),
        sa.Column('duration', sa.Float(), nullable=True),
        sa.Column('duration_waprice', sa.Integer(), nullable=True),
        sa.Column('has_put_option', sa.Integer(), nullable=True),
        sa.Column('has_call_option', sa.Integer(), nullable=True),
        sa.Column('maturity_date', sa.String(length=10), nullable=True),
        sa.Column('listing_level', sa.Integer(), nullable=True),
        sa.Column('bond_type', sa.Integer(), nullable=True),
        sa.Column('bond_kind', sa.Integer(), nullable=True),
        sa.Column('offer_date', sa.String(length=10), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=True),
        sa.Column('trading_status', sa.String(length=32), nullable=True),
        sa.Column('next_coupon', sa.String(length=10), nullable=True),
        sa.Column('board_name', sa.String(length=128), nullable=True),
        sa.Column('call_option_date', sa.String(length=10), nullable=True),
        sa.Column('put_option_date', sa.String(length=10), nullable=True),
        sa.Column('ratings', sa.String(), nullable=True),
    )
    
    op.create_table(
        'bondsecurity',
        sa.Column('secid', sa.String(length=64), primary_key=True),
        sa.Column('boardid', sa.String(length=32), nullable=True),
        sa.Column('prev_waprice', sa.Float(), nullable=True),
        sa.Column('yield_at_prev_waprice', sa.Float(), nullable=True),
        sa.Column('prev_price', sa.Float(), nullable=True),
        sa.Column('lot_size', sa.Integer(), nullable=True),
        sa.Column('reg_number', sa.String(), nullable=True),
        sa.Column('decimals', sa.Integer(), nullable=True),
        sa.Column('issue_size', sa.Integer(), nullable=True),
        sa.Column('prev_legal_close_price', sa.Float(), nullable=True),
        sa.Column('prev_date', sa.Date(), nullable=True),
        sa.Column('remarks', sa.String(), nullable=True),
        sa.Column('market_code', sa.String(), nullable=True),
        sa.Column('instr_id', sa.String(), nullable=True),
        sa.Column('sector_id', sa.String(), nullable=True),
        sa.Column('min_step', sa.Float(), nullable=True),
        sa.Column('face_unit', sa.String(), nullable=True),
        sa.Column('buyback_price', sa.Float(), nullable=True),
        sa.Column('buyback_date', sa.Date(), nullable=True),
        sa.Column('lat_name', sa.String(), nullable=True),
        sa.Column('issue_size_placed', sa.Integer(), nullable=True),
        sa.Column('sec_type', sa.String(), nullable=True),
        sa.Column('settle_date', sa.Date(), nullable=True),
        sa.Column('lot_value', sa.Float(), nullable=True),
        sa.Column('face_value_on_settle_date', sa.Float(), nullable=True),
        sa.Column('date_yield_from_issuer', sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(['secid'], ['bonds.secid']),
    )
    
    op.create_table(
        'bondmarketdata',
        sa.Column('secid', sa.String(length=64), primary_key=True),
        sa.Column('boardid', sa.String(length=32), nullable=True),
        sa.Column('bid', sa.Float(), nullable=True),
        sa.Column('offer', sa.Float(), nullable=True),
        sa.Column('spread', sa.Float(), nullable=True),
        sa.Column('bid_depth', sa.Integer(), nullable=True),
        sa.Column('offer_depth', sa.Integer(), nullable=True),
        sa.Column('open_price', sa.Float(), nullable=True),
        sa.Column('low', sa.Float(), nullable=True),
        sa.Column('high', sa.Float(), nullable=True),
        sa.Column('last_price', sa.Float(), nullable=True),
        sa.Column('last_change', sa.Float(), nullable=True),
        sa.Column('last_change_prcnt', sa.Float(), nullable=True),
        sa.Column('qty', sa.Integer(), nullable=True),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('value_usd', sa.Float(), nullable=True),
        sa.Column('waprice', sa.Float(), nullable=True),
        sa.Column('last_cnt_to_last_waprice', sa.Float(), nullable=True),
        sa.Column('wap_to_prev_waprice_prcnt', sa.Float(), nullable=True),
        sa.Column('wap_to_prev_waprice', sa.Float(), nullable=True),
        sa.Column('close_price', sa.Float(), nullable=True),
        sa.Column('market_price_today', sa.Float(), nullable=True),
        sa.Column('market_price', sa.Float(), nullable=True),
        sa.Column('last_to_prev_price', sa.Float(), nullable=True),
        sa.Column('num_trades', sa.Integer(), nullable=True),
        sa.Column('vol_today', sa.Integer(), nullable=True),
        sa.Column('val_today', sa.Float(), nullable=True),
        sa.Column('val_today_usd', sa.Float(), nullable=True),
        sa.Column('etf_settle_price', sa.Float(), nullable=True),
        sa.Column('update_time', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['secid'], ['bonds.secid']),
    )
    
    op.create_table(
        'bondmarketdatayield',
        sa.Column('secid', sa.String(length=64), primary_key=True),
        sa.Column('boardid', sa.String(length=32), nullable=True),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('yield_date', sa.String(length=10), nullable=True),
        sa.Column('zcyc_moment', sa.String(length=32), nullable=True),
        sa.Column('yield_date_type', sa.String(length=32), nullable=True),
        sa.Column('effective_yield', sa.Float(), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('zspread_bp', sa.Integer(), nullable=True),
        sa.Column('gspread_bp', sa.Integer(), nullable=True),
        sa.Column('waprice', sa.Float(), nullable=True),
        sa.Column('effective_yield_waprice', sa.Float(), nullable=True),
        sa.Column('duration_waprice', sa.Integer(), nullable=True),
        sa.Column('ir', sa.Float(), nullable=True),
        sa.Column('icpi', sa.Float(), nullable=True),
        sa.Column('bei', sa.Float(), nullable=True),
        sa.Column('cbr', sa.Float(), nullable=True),
        sa.Column('yield_to_offer', sa.Float(), nullable=True),
        sa.Column('yield_last_coupon', sa.Float(), nullable=True),
        sa.Column('trade_moment', sa.String(length=32), nullable=True),
        sa.Column('seqnum', sa.Integer(), nullable=True),
        sa.Column('systime', sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(['secid'], ['bonds.secid']),
    )
