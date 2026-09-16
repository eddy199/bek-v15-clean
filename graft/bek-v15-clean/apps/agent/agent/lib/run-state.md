# bek-v15-clean/apps/agent/agent/lib/run-state.ts

- LockedAgentRun · type · L4-L12 — type LockedAgentRun = { id: string; agentId: string; versionId: string; status: AgentRunStatus; sessionId: string | null; startedAt: Date | null; nextEventSequence: number; };
- lockAgentRun · function · L14-L26 — async function lockAgentRun( tx: Prisma.TransactionClient, runId: string, ): Promise<LockedAgentRun>
- runTerminalEventId · function · L28-L33 — function runTerminalEventId( runId: string, terminal: "completed" | "failed" | "cancelled", )
- isTerminalRunStatus · function · L41-L47 — function isTerminalRunStatus( status: AgentRunStatus, ): status is (typeof TERMINAL_RUN_STATUSES)[number]
