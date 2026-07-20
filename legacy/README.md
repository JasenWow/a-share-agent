# legacy/

无明确归属的待整理散件暂存区。重构期间作为中转，Phase 6 完成去留评估。

## 状态

🚧 **建设中** — 见根目录 `RESTRUCTURE-PLAN.md`

## 预期内容（Phase 1–4 迁入，Phase 6 评估去留）

| 路径 | 来源 | 去留倾向 |
|---|---|---|
| `scripts/validate_factor_mining.py` | 原 `scripts/` | **deprecated** — E2E，sys.path 伸手进 plugins/，耦合重 |
| `scripts/validate_evolution_loop.py` | 原 `scripts/` | **deprecated** — 同上 |
| `managed-agent-cookbooks/` | 原根目录 | **评估中** — 等待归属决策（进 plugins/ 或保留） |
| `openspec/` | 原根目录 | **评估中** — 是否复活 openspec 工作流 |
| `skills-lock.json` | 原根目录 | **重新生成** — 由 `scripts/sync-agent-skills.py` 重生 |

## 原则

- 每个进入 `legacy/` 的文件都要在本 README 标注去留倾向
- `deprecated` 文件加文件头注释说明替代方案（如有）
- `legacy/` 不是垃圾桶 —— Phase 6 必须清空或正式纳入结构
