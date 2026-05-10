---
description: Multi-factor stock screening — filter and rank A-share stocks by fundamental factors
argument-hint: "[filters] e.g. 'low PE high ROE' or 'PE<20 ROE>15'"
---

Load the `factor-screen` skill and screen A-share stocks based on user conditions.

Parse the argument for factor conditions. If no argument provided, ask the user:
1. "你想按哪些因子筛选？" (PE, PB, ROE, 营收增长, 股息率, 市值...)
2. "目标范围？" (全A / 沪深300 / 中证500 / 行业)
3. "排名数量？" (默认50只)

Apply A-share exclusion rules (ST/*ST, 停牌, 次新股) before any calculation.
