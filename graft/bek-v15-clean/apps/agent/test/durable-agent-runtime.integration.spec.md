# bek-v15-clean/apps/agent/test/durable-agent-runtime.integration.spec.ts

- createRun · function · L180-L200 — async function createRun( status: "QUEUED" | "RUNNING" = "RUNNING", startedAt: Date | null = new Date(), sessionId: string | null = null, triggerType: "MANUAL" | "EVENT" = "MANUAL", )
- satisfyRequiredActivity · function · L202-L210 — async function satisfyRequiredActivity(runId: string, callId: string)
- AuditHandler · type · L529-L544 — type AuditHandler = ( event: { type: string; data: object; meta: { id: string; at: string }; }, ctx: { session: { id: string; auth: { current: { attributes: Record<string, unknown> }; initiator: null; }; }; }, ) => Promise<void>;
- AuditHandler · type · L582-L598 — type AuditHandler = ( event: { type: string; data: object; meta: { id: string; at: string }; }, ctx: { session: { id: string; parent?: unknown; auth: { current: { attributes: Record<string, unknown> }; initiator: null; }; }; }, ) => Promise<void>;
- recordOf · function · L852-L856 — function recordOf(value: unknown): Record<string, unknown>
