# bek-v15-clean/apps/api/src/microsoft/outlook-sync.service.ts

- MailboxFailure · type · L37-L37 — type MailboxFailure<T> = Exclude<MailboxResult<T>, { outcome: "ok" }>;
- ExcludedFolders · type · L39-L41 — type ExcludedFolders = | { outcome: "ok"; ids: Set<string> } | { outcome: "lookup-failed"; failure: MailboxFailure<GraphFolder> };
- OutlookSyncOutcome · type · L43-L49 — type OutlookSyncOutcome = { source: "outlook"; userId: string; status: "synced" | "skipped" | "reconnect" | "rate-limited" | "failed"; messagesWritten?: number; reason?: string; };
- OutlookSyncService · class · L52-L362 — class OutlookSyncService
- constructor · method · L55-L60 — constructor( private readonly graph: GraphClient, private readonly tokens: MailboxTokenService, private readonly state: SyncStateService, private readonly threads: ThreadWriterService, )
- sync · method · L62-L117 — async sync(row: MailboxSync): Promise<OutlookSyncOutcome>
- start · method · L119-L134 — private async start( row: MailboxSync, initializedAt: Date, ): Promise<OutlookSyncOutcome>
- incremental · method · L136-L232 — private async incremental( row: MailboxSync, accessToken: string, mailbox: string, cursor: string, ): Promise<OutlookSyncOutcome>
- excludedFolderIds · method · L234-L253 — private async excludedFolderIds( accessToken: string, ): Promise<ExcludedFolders>
- parse · method · L255-L287 — private parse(message: GraphMessage): IncomingMessage | null
- rootIdOf · method · L289-L318 — private rootIdOf(message: GraphMessage, internetMessageId: string): string
- value · function · L292-L298 — value = (name: string): string | null
- sentAt · method · L320-L328 — private sentAt(message: GraphMessage): Date | null
- handleFailure · method · L330-L361 — private async handleFailure( row: MailboxSync, result: { outcome: string; reason: string; retryAfterMs?: number }, ): Promise<OutlookSyncOutcome>
- isMissingFolder · function · L364-L366 — function isMissingFolder(failure: MailboxFailure<GraphFolder>): boolean
- addressOf · function · L368-L375 — function addressOf(entry: GraphAddress | undefined): Participant | null
- addressList · function · L377-L394 — function addressList( entries: GraphAddress[] | undefined, kind: "to" | "cc", ): { email: string; name: string | null; kind: "to" | "cc" }[]
