# bek-v15-clean/apps/api/src/mailbox/thread-writer.service.ts

- IncomingMessage · type · L21-L32 — type IncomingMessage = { rfcMessageId: string; rootId: string; subject: string | null; from: Participant; recipients: { email: string; name: string | null; kind: "to" | "cc" }[]; body: string; sentAt: Date; gmailMessageId?: string | null; outlookMessageId?: string | null; outlookWebLink?: string | null; };
- ThreadWriterService · class · L35-L292 — class ThreadWriterService
- constructor · method · L38-L42 — constructor( @InjectDatabase() private readonly db: Db, private readonly match: MailboxMatchService, private readonly stamp: ActivityStampService, )
- context · method · L44-L57 — async context(): Promise<MatchContext>
- store · method · L59-L204 — async store( row: MailboxSync, options: { mailbox: string; origin: SyncSource }, parsed: IncomingMessage, context: MatchContext, ): Promise<boolean>
- storedElsewhere · method · L206-L221 — private async storedElsewhere( error: unknown, rfcMessageId: string, ): Promise<boolean>
- touch · method · L223-L240 — private async touch( target: { companyId: string | null; contactId: string | null }, at: Date, rfcMessageId: string, ): Promise<void>
- hasOutboundInThread · method · L242-L255 — private async hasOutboundInThread( rootMessageId: string, mailbox: string, ): Promise<boolean>
- project · method · L257-L291 — private async project( tx: Prisma.TransactionClient, emailThreadId: string, userId: string, summary: { subject: string; snippet: string | null; lastMessageAt: Date; companyId: string | null; contactId: string | null; origin: SyncSource; }, ): Promise<Date>
