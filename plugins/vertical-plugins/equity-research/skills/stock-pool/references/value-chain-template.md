---
name: value-chain-template
description: Output format template for Step 1 theme value chain analysis
---

# 价值链分析输出模板

Agent 在 Step 1 结束时按此 JSON 格式输出价值链分析结果。

## JSON Schema

```json
{
  "theme": "主题名称",
  "analysis_date": "YYYY-MM-DD",
  "value_chain": [
    {
      "stage": "产业链环节名称",
      "value_density": "高|中|低",
      "barrier": "壁垒简述",
      "companies": [
        {
          "code": "000000.SZ",
          "name": "公司名称",
          "type": "pure_play | concept | second_order",
          "market_position": "市场地位描述",
          "note": "补充说明"
        }
      ]
    }
  ],
  "market_landscape": {
    "total_addressable_market": "xxx 亿",
    "growth_rate": "CAGR xx%",
    "key_players": ["公司A", "公司B", "公司C"]
  }
}
```

## Type Definitions

| Type | Definition |
|------|-----------|
| `pure_play` | 主题相关营收占比 > 30%，或被市场公认为该主题核心标的 |
| `concept` | 概念板块成员但主营占比 < 20%，弹性大但确定性低 |
| `second_order` | 供应链受益，不直接面对终端市场 |

## Example: 机器人

```json
{
  "theme": "机器人",
  "analysis_date": "2026-05-21",
  "value_chain": [
    {
      "stage": "核心零部件",
      "value_density": "高",
      "barrier": "精密加工技术壁垒高，国产替代空间大",
      "companies": [
        {
          "code": "300124.SZ",
          "name": "汇川技术",
          "type": "pure_play",
          "market_position": "伺服龙头，国内市占率前三",
          "note": "人形机器人关节电机核心供应商"
        },
        {
          "code": "002472.SZ",
          "name": "双环传动",
          "type": "second_order",
          "market_position": "RV减速器国内领先",
          "note": "工业机器人+人形机器人双线布局"
        }
      ]
    },
    {
      "stage": "整机制造",
      "value_density": "中",
      "barrier": "系统集成能力要求高，但竞争加剧",
      "companies": [
        {
          "code": "300015.SZ",
          "name": "埃斯顿",
          "type": "pure_play",
          "market_position": "国产工业机器人龙头",
          "note": "全产业链布局，伺服+本体+集成"
        }
      ]
    }
  ],
  "market_landscape": {
    "total_addressable_market": "约 800 亿",
    "growth_rate": "CAGR 25%+",
    "key_players": ["汇川技术", "埃斯顿", "绿的谐波"]
  }
}
```
