# bek-v15-clean/apps/api/src/google/calendar-sync.service.ts

- SyncOutcome · type · L30-L37 — type SyncOutcome = { source: "calendar"; userId: string; status: "synced" | "skipped" | "reconnect" | "rate-limited" | "failed"; eventsWritten?: number; eventsRemoved?: number; reason?: string; };
- CalendarSyncService · class · L40-L435 — class CalendarSyncService
- constructor · method · L43-L51 — constructor( @InjectDatabase() private readonly db: Db, private readonly calendar: CalendarClient, private readonly tokens: MailboxTokenService, private readonly match: MailboxMatchService, private readonly state: SyncStateService, private readonly stamp: ActivityStampService, private readonly agent: AgentTriggerService, )
- sync · method · L53-L189 — async sync(row: MailboxSync): Promise<SyncOutcome>
- apply · method · L191-L293 — private async apply( event: GoogleEvent, row: MailboxSync, context: MatchContext, ): Promise<"written" | "removed" | "ignored">
- syncAttendees · method · L295-L342 — private async syncAttendees( eventId: string, event: GoogleEvent, ): Promise<void>
- prepareForMeeting · method · L344-L365 — private async prepareForMeeting( eventId: string, startsAt: Date, ): Promise<void>
- project · method · L367-L407 — private async project( calendarEventId: string, userId: string, summary: { title: string; startsAt: Date; companyId: string | null; contactId: string | null; location: string | null; }, ): Promise<void>
- participantsOf · method · L409-L428 — private participantsOf(event: GoogleEvent): Participant[]
- horizon · method · L430-L434 — private horizon(): Date
