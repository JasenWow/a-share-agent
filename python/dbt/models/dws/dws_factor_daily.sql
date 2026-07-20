-- DWS: 每日因子值（量化研究基础）
-- 因子：动量 20d / 波动率 20d / 换手率代理（volume/shares 简化为 volume 均值）

with windowed as (
    select
        trade_date,
        code,
        exchange,
        close,
        daily_return,
        volume,
        -- 20 日动量：当日收盘 / 20 日前收盘 - 1
        close / lag(close, 20) over (partition by code order by trade_date) - 1 as momentum_20d,
        -- 20 日收益率波动率（标准差）
        stddev(daily_return) over (
            partition by code order by trade_date
            rows between 20 preceding and 1 preceding
        ) as volatility_20d,
        -- 20 日成交量均值（换手代理）
        avg(volume) over (
            partition by code order by trade_date
            rows between 20 preceding and 1 preceding
        ) as avg_volume_20d
    from {{ ref('dwd_equity_daily') }}
)

select
    trade_date,
    code,
    exchange,
    -- 动量因子（百分比）
    momentum_20d * 100 as momentum_20d_pct,
    -- 波动率因子（日波动 × sqrt(252) 年化）
    volatility_20d * sqrt(252) * 100 as volatility_20d_pct,
    -- 换手代理因子
    avg_volume_20d as avg_volume_20d
from windowed
where momentum_20d is not null  -- 前 20 日没有数据则动量无意义
