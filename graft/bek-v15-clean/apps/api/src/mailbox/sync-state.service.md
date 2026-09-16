# bek-v15-clean/apps/api/src/mailbox/sync-state.service.ts

- SyncStateService · class · L13-L171 — class SyncStateService
- constructor · method · L16-L16 — constructor(@InjectDatabase() private readonly db: Db)
- get · method · L18-L22 — async get(userId: string, source: SyncSource): Promise<MailboxSync | null>
- listForUser · method · L24-L31 — async listForUser( userId: string, sources?: readonly SyncSource[], ): Promise<MailboxSync[]>
- due · method · L33-L38 — async due(now: Date): Promise<MailboxSync[]>
- claim · method · L40-L50 — async claim(row: MailboxSync, now: Date): Promise<boolean>
- release · method · L52-L57 — async release(id: string): Promise<void>
- ensure · method · L59-L78 — async ensure( userId: string, source: SyncSource, options: { autoCreate: boolean }, ): Promise<MailboxSync>
- markRunning · method · L80-L85 — async markRunning(id: string): Promise<void>
- settle · method · L87-L103 — async settle( id: string, update: { cursor?: string | null; status: GoogleSyncStatus; }, ): Promise<void>
- clearCursor · method · L105-L121 — async clearCursor(id: string, reason: string): Promise<void>
- markNeedsReconnect · method · L123-L132 — async markNeedsReconnect(id: string, reason: string): Promise<void>
- markRateLimited · method · L134-L142 — async markRateLimited(id: string, retryAfterMs: number): Promise<void>
- markFailed · method · L144-L153 — async markFailed(id: string, reason: string): Promise<void>
- setAutoCreate · method · L155-L164 — async setAutoCreate( userId: string, source: SyncSource, enabled: boolean, ): Promise<void>
- remove · method · L166-L170 — async remove(userId: string, source?: SyncSource): Promise<void>
- dueWhere · function · L173-L178 — function dueWhere(now: Date)
