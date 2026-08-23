# AGENT_WORKSPACE_v15/uploads/events.ts

- installDaily · function · L32-L44 — async function installDaily( properties: Properties, at = new Date(), ): Promise<boolean>
- milestone · function · L46-L65 — async function milestone(step: Milestone, at?: Date): Promise<boolean>
- agentError · function · L67-L79 — function agentError(input: { error: unknown; tool?: string | null; taskKind?: string | null; source?: "tool" | "session" | "turn"; }): void
- syncError · function · L81-L87 — function syncError(input: { error: unknown; source: string }): void
- apiError · function · L89-L100 — function apiError(input: { error: unknown; route: string | null; status: number; }): void
- modelError · function · L102-L111 — function modelError(input: { error: unknown; modelId?: string | null; }): void
