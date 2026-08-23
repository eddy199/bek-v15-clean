# bek-v15-clean/apps/agent/agent/lib/tasks.ts

- LeasedTask · type · L5-L17 — type LeasedTask = { id: string; contactId: string | null; companyId: string | null; dealId: string | null; kind: string; reason: string; payload: Prisma.JsonValue | null; budget: number; attempts: number; priority: number; dueAt: Date; };
- TaskSubject · type · L19-L25 — type TaskSubject = { id: string; contactId: string | null; companyId: string | null; dealId: string | null; kind: string; };
- claimDue · function · L31-L71 — async function claimDue( limit: number, kinds: { only: readonly string[] } | { except: readonly string[] }, leaseMs = LEASE_MS, ): Promise<LeasedTask[]>
- retireExhausted · function · L73-L85 — async function retireExhausted(): Promise<TaskSubject[]>
- completeTask · function · L87-L113 — async function completeTask( taskId: string, outcome: string, sessionId?: string, ): Promise<TaskSubject | null>
- taskSubject · function · L115-L126 — async function taskSubject(taskId: string): Promise<TaskSubject | null>
- noteSession · function · L128-L136 — async function noteSession( taskId: string, sessionId: string, ): Promise<void>
- scheduleTask · function · L138-L182 — async function scheduleTask(input: { contactId?: string | null; companyId?: string | null; dealId?: string | null; kind: string; reason: string; payload?: Prisma.InputJsonValue | null; dueAt: Date; priority?: number; budget?: number; }): Promise<{ id: string }>
- lastDecision · function · L184-L196 — async function lastDecision(contactId: string)
