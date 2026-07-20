-- DWD: 财务季度宽表（利润表展开 + 派生指标）
-- 派生：毛利率（简化版用 oper_profit/revenue）、净利率、取最新披露版本

with ranked as (
    select
        *,
        -- 同一 code + end_date 可能多次修订（update_flag），取最新 ann_date
        row_number() over (
            partition by code, end_date
            order by ann_date desc, update_flag desc
        ) as rn
    from {{ ref('stg_financial_income') }}
    where revenue > 0  -- 过滤无效记录
)

select
    code,
    exchange,
    ann_date,
    end_date,
    period,
    revenue,
    oper_profit,
    n_income,
    n_income_attr_p,
    -- 派生：营业利润率
    case when revenue > 0 then oper_profit / revenue * 100 else null end as oper_margin_pct,
    -- 派生：净利率（归母）
    case when revenue > 0 then n_income_attr_p / revenue * 100 else null end as net_margin_pct
from ranked
where rn = 1  -- 仅保留最新版本
