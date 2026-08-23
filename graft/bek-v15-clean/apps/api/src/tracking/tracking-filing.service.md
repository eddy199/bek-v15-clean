# bek-v15-clean/apps/api/src/tracking/tracking-filing.service.ts

- columns · function · L23-L39 — function columns( touch: Touch | undefined, prefix: "first" | "last", ): Record<string, string | Date | null>
- FilingOutcome · type · L41-L43 — type FilingOutcome = | { filed: true; contactId: string } | { filed: false; reason: string };
- TrackingFilingService · class · L46-L261 — class TrackingFilingService
- constructor · method · L49-L55 — constructor( @InjectDatabase() private readonly db: Db, private readonly counters: TrackingCounterService, private readonly companies: CompanyDirectoryService, private readonly agent: AgentTriggerService, private readonly stamp: ActivityStampService, )
- file · method · L57-L144 — async file(submission: { id: string; email: string | null; host: string; visitorId: string | null; name: string | null; firstTouch?: Touch; lastTouch?: Touch; }): Promise<FilingOutcome>
- raced · method · L146-L161 — private async raced( error: unknown, email: string, ): Promise<{ id: string } | null>
- attach · method · L163-L214 — private async attach( submissionId: string, contactId: string, context: { visitorId: string | null; firstTouch?: Touch; lastTouch?: Touch; }, ): Promise<void>
- author · method · L216-L227 — private async author(contactId: string): Promise<string | null>
- skip · method · L229-L239 — private async skip( submissionId: string, reason: string, ): Promise<FilingOutcome>
- suppressed · method · L241-L260 — private async suppressed( email: string, domain: string, ): Promise<string | null>
