# bek-v15-clean/apps/agent/agent/hooks/audit.ts

- "*" · method · L10-L50 — async "*"(event, ctx)
- persistBuilderLifecycle · function · L54-L83 — async function persistBuilderLifecycle( tx: Prisma.TransactionClient, event: { type: string }, sessionId: string, ctx: Parameters<typeof purposeOf>[0], )
- persistRunEvent · function · L85-L175 — async function persistRunEvent( tx: Prisma.TransactionClient, eventId: string, type: string, data: object, emittedAt: Date, ctx: Parameters<typeof purposeOf>[0] & { session: { id: string } }, )
- isRootSession · function · L177-L179 — function isRootSession(ctx: Parameters<typeof purposeOf>[0]): boolean
- recordOf · function · L181-L185 — function recordOf(value: unknown): Record<string, unknown>
- numberOf · function · L187-L189 — function numberOf(value: unknown): number | null
