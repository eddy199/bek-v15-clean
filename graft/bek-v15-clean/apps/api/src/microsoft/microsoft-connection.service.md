# bek-v15-clean/apps/api/src/microsoft/microsoft-connection.service.ts

- SourceStatus · type · L17-L24 — type SourceStatus = { source: MicrosoftSyncSource; connected: boolean; status: GoogleSyncStatus | null; lastSyncedAt: string | null; lastError: string | null; autoCreate: boolean; };
- ConnectionStatus · type · L26-L32 — type ConnectionStatus = { configured: boolean; linked: boolean; required: boolean; hasRefreshToken: boolean; sources: SourceStatus[]; };
- MicrosoftConnectionService · class · L35-L182 — class MicrosoftConnectionService
- constructor · method · L38-L43 — constructor( @InjectDatabase() private readonly db: Db, private readonly tokens: MailboxTokenService, private readonly state: SyncStateService, private readonly stamp: ActivityStampService, )
- status · method · L45-L80 — async status(userId: string): Promise<ConnectionStatus>
- onConnected · method · L82-L108 — async onConnected(userId: string): Promise<void>
- reconcileAll · method · L110-L124 — async reconcileAll(): Promise<void>
- purgeSyncedData · method · L126-L159 — async purgeSyncedData(userId: string): Promise<{ purged: number }>
- revoke · method · L161-L168 — async revoke(userId: string): Promise<{ revoked: boolean }>
- setAutoCreate · method · L170-L181 — async setAutoCreate( userId: string, source: MicrosoftSyncSource, enabled: boolean, ): Promise<void>
- rebuildThreads · function · L184-L224 — async function rebuildThreads( tx: Prisma.TransactionClient, threadIds: string[], ): Promise<void>
