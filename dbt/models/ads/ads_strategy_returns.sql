-- ADS: 策略净值序列（等权 Top-2 动量策略）
-- 简化版：每月末选全市场动量前 2 名，等权持有，记录月度净值
-- 这是 demo 策略，非投资建议；真实策略交给 backtest-engine

-- 1. 每月动量排名（用月末可得的 momentum_20d_pct）
with monthly_factor as (
    select
        substr(f.trade_date, 1, 6) as year_month,
        f.code,
        f.exchange,
        f.momentum_20d_pct,
        -- 每月最后一个交易日的动量值（粗略：取当月任意一天，因月内变化小）
        row_number() over (
            partition by substr(f.trade_date, 1, 6), f.code
            order by f.trade_date desc
        ) as rn_code
    from {{ ref('dws_factor_daily') }} f
),

month_end_factor as (
    select year_month, code, exchange, momentum_20d_pct
    from monthly_factor
    where rn_code = 1
),

-- 2. 每月选 Top-2 动量
top_picks as (
    select
        year_month,
        code,
        exchange,
        momentum_20d_pct,
        row_number() over (partition by year_month order by momentum_20d_pct desc) as rank
    from month_end_factor
    qualify rank <= 2  -- DuckDB 支持 QUALIFY
),

-- 3. 关联月度收益
strategy_returns as (
    select
        t.year_month,
        t.code,
        t.exchange,
        m.monthly_return_pct,
        t.rank
    from top_picks t
    left join {{ ref('dws_equity_monthly') }} m
        on t.code = m.code
        and t.year_month = m.year_month
)

select
    year_month,
    code,
    exchange,
    monthly_return_pct as strategy_return_pct,
    rank as momentum_rank
from strategy_returns
order by year_month, rank
