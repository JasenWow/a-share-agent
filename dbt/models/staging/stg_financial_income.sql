-- Staging: 标准化利润表数据

with source as (
    select * from {{ ref('seed_financial_income') }}
)

select
    cast(code as varchar) as code,
    cast(exchange as varchar) as exchange,
    cast(ann_date as varchar) as ann_date,
    cast(end_date as varchar) as end_date,
    cast(period as varchar) as period,
    cast(update_flag as varchar) as update_flag,
    cast(revenue as double) as revenue,
    cast(oper_profit as double) as oper_profit,
    cast(n_income as double) as n_income,
    cast(n_income_attr_p as double) as n_income_attr_p
from source
