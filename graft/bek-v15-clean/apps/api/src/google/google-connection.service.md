# bek-v15-clean/apps/api/src/google/google-connection.service.ts

- SourceStatus · type · L19-L26 — type SourceStatus = { source: GoogleSyncSource; connected: boolean; status: GoogleSyncStatus | null; lastSyncedAt: string | null; lastError: string | null; autoCreate: boolean; };
- ConnectionStatus · type · L28-L34 — type ConnectionStatus = { configured: boolean; linked: boolean; required: boolean; hasRefreshToken: boolean; sources: SourceStatus[]; };
- GoogleConnectionService · class · L37-L234 — class GoogleConnectionService
- constructor · method · L40-L46 — constructor( @InjectDatabase() private readonly db: Db, private readonly tokens: MailboxTokenService, private readonly state: SyncStateService, private readonly match: MailboxMatchService, private readonly stamp: ActivityStampService, )
- status · method · L48-L83 — async status(userId: string): Promise<ConnectionStatus>
- onConnected · method · L85-L109 — async onConnected(userId: string): Promise<void>
- reconcileAll · method · L111-L125 — async reconcileAll(): Promise<void>
- purgeSyncedData · method · L127-L164 — async purgeSyncedData(userId: string): Promise<{ purged: number }>
- revoke · method · L166-L173 — async revoke(userId: string): Promise<{ revoked: boolean }>
- setAutoCreate · method · L175-L186 — async setAutoCreate( userId: string, source: GoogleSyncSource, enabled: boolean, ): Promise<void>
- suppressDomain · method · L188-L233 — async suppressDomain( domain: string, options: { reason?: string; purge: boolean }, ): Promise<{ domain: string; purged: number }>
- rebuildThreads · function · L236-L276 — async function rebuildThreads( tx: Prisma.TransactionClient, threadIds: string[], ): Promise<void>
