# bek-v15-clean/apps/api/src/sync/mailbox-sync.service.ts

- TickSummary · type · L15-L22 — type TickSummary = { attempted: number; synced: number; skipped: number; rateLimited: number; failed: number; durationMs: number; };
- MailboxSyncService · class · L25-L124 — class MailboxSyncService
- constructor · method · L28-L34 — constructor( private readonly state: SyncStateService, private readonly google: GoogleSyncService, private readonly microsoft: MicrosoftSyncService, private readonly googleConnections: GoogleConnectionService, private readonly microsoftConnections: MicrosoftConnectionService, )
- runDue · method · L36-L113 — async runDue(): Promise<TickSummary>
- runOne · method · L115-L123 — private async runOne(userId: string, source: string)
