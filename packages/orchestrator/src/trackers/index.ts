export * from "./tracker"
// Both trackers are live: each emits one daily WorkItem per local day.
//   - factor-mining: weekday-themed factor discovery; injects active factor
//     expressions as dedup context; instructs the agent to persist |IC|>0.03
//     findings as candidates via `aquan factor register`.
//   - free-exploration: daily market observation summary.
export * from "./factor-mining"
export * from "./free-exploration"
