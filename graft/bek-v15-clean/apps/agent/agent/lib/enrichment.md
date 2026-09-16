# bek-v15-clean/apps/agent/agent/lib/enrichment.ts

- SettleGuard · type · L4-L10 — type SettleGuard = { enrichmentStatus?: EnrichmentStatus; OR?: Array<{ enrichmentStatus: EnrichmentStatus; updatedAt?: { lt: Date }; }>; };
- markRunning · function · L12-L14 — async function markRunning(subject: TaskSubject): Promise<void>
- settle · function · L16-L22 — async function settle( subject: TaskSubject, status: EnrichmentStatus, error?: string, ): Promise<void>
- write · function · L24-L55 — async function write( subject: TaskSubject, status: EnrichmentStatus, error: string | null, onlyIfRunning: boolean, ): Promise<void>
- settleable · function · L57-L77 — async function settleable( subject: TaskSubject, status: EnrichmentStatus, ): Promise<SettleGuard>
- taskEndedAt · function · L79-L86 — async function taskEndedAt(taskId: string): Promise<Date | null>
- hasOpenRequest · function · L88-L100 — async function hasOpenRequest(subject: TaskSubject): Promise<boolean>
