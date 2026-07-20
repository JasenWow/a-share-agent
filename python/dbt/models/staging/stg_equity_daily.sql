-- Staging: 标准化日线数据
-- MVP 阶段从 seed 读（真实 ETL 跑过后切回 source ods.ods_equity_daily）
-- 切换方式：把下面 select 改为 from source ods.ods_equity_daily（用 jinja source ref）

with source as (
    select * from {{ ref('seed_equity_daily') }}
)

select
    cast(trade_date as varchar) as trade_date,
    cast(code as varchar) as code,
    cast(exchange as varchar) as exchange,
    cast(open as double) as open,
    cast(high as double) as high,
    cast(low as double) as low,
    cast(close as double) as close,
    cast(volume as double) as volume,
    cast(amount as double) as amount,
    cast(pct_chg as double) as pct_chg
from source
