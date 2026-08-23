# bek-v15-clean/apps/agent/agent/lib/dispatch.ts

- retireAbandoned · function · L29-L45 — async function retireAbandoned(): Promise<void>
- runVisibleLane · function · L47-L66 — async function runVisibleLane(signal?: AbortSignal): Promise<number>
- DirectOutcome · type · L68-L68 — type DirectOutcome = { finished: true } | { finished: false; reason: string };
- runDirect · function · L70-L93 — async function runDirect( task: LeasedTask, handle: (task: LeasedTask) => Promise<void> = handleDirect, timeoutMs: number = DISPATCH.sweep.itemTimeoutMs, ): Promise<void>
- reconcileDirect · function · L95-L102 — async function reconcileDirect( task: LeasedTask, outcome: DirectOutcome, ): Promise<void>
- handleDirect · function · L104-L150 — async function handleDirect(task: LeasedTask): Promise<void>
- runResearchLane · function · L152-L176 — async function runResearchLane( start: (task: LeasedTask) => Promise<{ id: string }>, signal?: AbortSignal, ): Promise<number>
- StartOutcome · type · L178-L180 — type StartOutcome = | { accepted: true; sessionId: string } | { accepted: false; reason: string };
- beginResearch · function · L182-L213 — async function beginResearch( task: LeasedTask, start: (task: LeasedTask) => Promise<{ id: string }>, ): Promise<void>
- reconcileStart · function · L215-L225 — async function reconcileStart( task: LeasedTask, outcome: StartOutcome, ): Promise<void>
- linkSession · function · L227-L253 — async function linkSession( task: LeasedTask, sessionId: string, note: (taskId: string, sessionId: string) => Promise<void> = noteSession, link: { attempts: number; retryMs: number } = DISPATCH.research.link, ): Promise<boolean>
- reasonOf · function · L255-L257 — function reasonOf(error: unknown): string
- taskAuth · function · L259-L271 — function taskAuth(task: LeasedTask, base: AppAuth = APP_AUTH): AppAuth
- oldestUnsettledAt · function · L285-L295 — function oldestUnsettledAt(): Date | null
- dispatchHealth · function · L297-L324 — function dispatchHealth()
- brief · function · L401-L408 — function brief(task: LeasedTask): string
- work · function · L410-L426 — function work(kind: string, reason: string): string
