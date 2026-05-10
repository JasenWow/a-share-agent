---
name: xlsx-author
description: |
  Generate .xlsx files with professional formatting for A-share analysis outputs.
  Used by all agents that produce Excel deliverables.
  Write to ./out/ directory and return relative path.
---

# Excel File Authoring

## Output Convention

- Write to `./out/<name>_<date>.xlsx`
- Date format: YYYYMMDD
- Return the relative path in final message

## Color Coding

| Color | Hex | Usage |
|-------|-----|-------|
| Blue | #0000FF | Input cells (hardcoded values) |
| Black | #000000 | Formula cells |
| Green | #008000 | Linked/reference cells |
| Red | #FF0000 | Warnings / negative values |
| Gray | #808080 | Headers / labels |

## Formatting Standards

- Header row: bold, background #1F4E79, white text
- Number format: #,##0 for integers, #,##0.00 for decimals, 0.00% for percentages
- Column width: auto-fit based on content
- Freeze panes: freeze top header row
- Print area: set to data range

## A-Share Specific

- All monetary values in CNY (¥), not USD
- Use Chinese stock codes: 6-digit (e.g., 600519, 000001)
- Stock names in Chinese
- Industry names in Chinese (申万一级)
