# bek-v15-clean/apps/agent/agent/hooks/activity.ts

- ActionRequest · type · L3-L3 — type ActionRequest = HookEvent<"actions.requested">["data"]["actions"][number];
- ActionResult · type · L4-L4 — type ActionResult = HookEvent<"action.result">["data"]["result"];
- truncate · function · L11-L13 — function truncate(text: string, limit: number): string
- line · function · L15-L17 — function line(symbol: string, text: string): void
- preview · function · L19-L31 — function preview(input: unknown): string
- requestName · function · L33-L44 — function requestName(action: ActionRequest): string
- resultName · function · L46-L55 — function resultName(result: ActionResult): string
- count · function · L57-L59 — function count(tokens: number): string
- "session.started" · method · L63-L71 — "session.started"(event, ctx)
- "message.received" · method · L73-L80 — "message.received"(event)
- "actions.requested" · method · L82-L94 — "actions.requested"(event)
- "action.result" · method · L96-L114 — "action.result"(event)
- "message.completed" · method · L116-L125 — "message.completed"(event)
- "step.completed" · method · L127-L150 — "step.completed"(event)
- "step.failed" · method · L152-L157 — "step.failed"(event)
- "turn.failed" · method · L159-L164 — "turn.failed"(event)
- "session.failed" · method · L166-L171 — "session.failed"(event)
