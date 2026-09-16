# bek-v15-clean/apps/api/src/google/gmail-sync.service.ts

- GmailSyncOutcome · type · L30-L37 — type GmailSyncOutcome = { source: "gmail"; userId: string; status: "synced" | "skipped" | "reconnect" | "rate-limited" | "failed"; messagesWritten?: number; threadsTouched?: number; reason?: string; };
- GmailSyncService · class · L40-L322 — class GmailSyncService
- constructor · method · L43-L49 — constructor( @InjectDatabase() private readonly db: Db, private readonly gmail: GmailClient, private readonly tokens: MailboxTokenService, private readonly state: SyncStateService, private readonly threads: ThreadWriterService, )
- sync · method · L51-L96 — async sync(row: MailboxSync): Promise<GmailSyncOutcome>
- start · method · L98-L123 — private async start( row: MailboxSync, historyId: string | null, ): Promise<GmailSyncOutcome>
- incremental · method · L125-L187 — private async incremental( row: MailboxSync, accessToken: string, mailbox: string, startHistoryId: string, ): Promise<GmailSyncOutcome>
- ingest · method · L189-L232 — private async ingest( row: MailboxSync, accessToken: string, mailbox: string, ids: readonly string[], ): Promise<{ written: number; remaining: number }>
- parse · method · L234-L272 — private parse(message: GmailMessage): IncomingMessage | null
- sentAt · method · L274-L288 — private sentAt( message: GmailMessage, headers: readonly GmailHeader[] | undefined, ): Date | null
- handleFailure · method · L290-L321 — private async handleFailure( row: MailboxSync, result: { outcome: string; reason: string; retryAfterMs?: number }, ): Promise<GmailSyncOutcome>
