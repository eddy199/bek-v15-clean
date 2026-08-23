# bek-v15-clean/apps/agent/agent/channels/crm.ts

- authorised · function · L37-L47 — function authorised(request: Request): boolean
- taskToken · function · L49-L51 — function taskToken(taskId: string): string
- taskFromToken · function · L53-L61 — function taskFromToken(token: string | undefined): string | null
- "input.requested" · method · L206-L212 — async "input.requested"(data, channel, ctx)
- "message.completed" · method · L214-L228 — async "message.completed"(data, channel)
- "session.waiting" · method · L230-L247 — async "session.waiting"(_data, channel)
- "turn.failed" · method · L249-L277 — async "turn.failed"(data, channel)
- "session.completed" · method · L279-L312 — async "session.completed"(_data, channel)
- "turn.cancelled" · method · L314-L336 — async "turn.cancelled"(_data, channel)
- "session.failed" · method · L338-L356 — async "session.failed"(data, channel)
- receive · method · L359-L385 — async receive(input, { send })
- assertInternalDispatchAuth · function · L388-L397 — function assertInternalDispatchAuth(value: unknown): void
- recordOf · function · L399-L403 — function recordOf(value: unknown): Record<string, unknown>
