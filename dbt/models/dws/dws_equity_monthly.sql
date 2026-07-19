-- DWS: 个股月度汇总（OHLCV + 月收益）
-- 月度按 trade_date 前 6 位（YYYYMM）分组

with monthly_agg as (
    select
        code,
        exchange,
        substr(trade_date, 1, 6) as year_month,
        -- 月度 OHLC：open 取第一条，close 取最后一条，high/max low/min
        -- 用 arg_min/arg_max（DuckDB 原生）按 trade_date 取首尾
        arg_min(open, trade_date) as month_open,
        arg_max(close, trade_date) as month_close,
        max(high) as month_high,
        min(low) as month_low,
        sum(volume) as month_volume,
        sum(amount) as month_amount,
        count(*) as trading_days
    from {{ ref('dwd_equity_daily') }}
    group by code, exchange, substr(trade_date, 1, 6)
)

select
    code,
    exchange,
    year_month,
    month_open,
    month_high,
    month_low,
    month_close,
    month_volume,
    month_amount,
    trading_days,
    -- 月收益率（%）
    case
        when month_open > 0 then (month_close - month_open) / month_open * 100
        else null
    end as monthly_return_pct
from monthly_agg
