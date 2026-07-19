-- DWD: 日线明细宽表
-- 派生：日收益率、vwap、是否涨停（主板 ±10% / 创业板科创板 ±20%）
-- 注：本表基于未复权数据，复权派生留给后续业务层

with base as (
    select
        *,
        -- 日收益率（基于前收 / 当收，pct_chg 已提供，这里直接用）
        pct_chg / 100.0 as daily_return,
        -- VWAP：成交额 / 成交量（股），volume 单位为股
        case when volume > 0 then amount / volume else null end as vwap,
        -- 涨停判断：当日涨幅 ≥ 9.9% 视为涨停（简化版，未区分 ST/创业板）
        case
            when pct_chg >= 9.9 then true
            when pct_chg <= -9.9 then true  -- 跌停
            else false
        end as is_limit
    from {{ ref('stg_equity_daily') }}
)

select
    trade_date,
    code,
    exchange,
    open,
    high,
    low,
    close,
    volume,
    amount,
    pct_chg,
    daily_return,
    vwap,
    is_limit,
    -- 派生：收盘相对开盘涨跌（日内动量）
    case when open > 0 then (close - open) / open * 100 else null end as intraday_pct
from base
