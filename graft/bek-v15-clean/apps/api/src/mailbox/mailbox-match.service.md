# bek-v15-clean/apps/api/src/mailbox/mailbox-match.service.ts

- SyncRecordSource · type · L18-L20 — type SyncRecordSource = | typeof RecordSource.EMAIL | typeof RecordSource.CALENDAR;
- MatchResult · type · L22-L26 — type MatchResult = { companyId: string | null; contactId: string | null; external: Participant[]; };
- MatchContext · type · L28-L33 — type MatchContext = { ourAddresses: ReadonlySet<string>; ourDomains: ReadonlySet<string>; suppressedDomains: ReadonlySet<string>; suppressedEmails: ReadonlySet<string>; };
- MatchRequest · type · L35-L40 — type MatchRequest = { participants: readonly Participant[]; allowCreate: boolean; source: SyncRecordSource; ownerId: string; };
- MailboxMatchService · class · L43-L300 — class MailboxMatchService
- constructor · method · L46-L51 — constructor( @InjectDatabase() private readonly db: Db, private readonly companies: CompanyDirectoryService, private readonly agent: AgentTriggerService, private readonly log: EnrichmentLogService, )
- internalIdentity · method · L53-L71 — async internalIdentity(): Promise<{ addresses: Set<string>; domains: Set<string>; }>
- suppressedDomains · method · L73-L78 — async suppressedDomains(): Promise<Set<string>>
- suppressedEmails · method · L80-L85 — async suppressedEmails(): Promise<Set<string>>
- resolve · method · L87-L153 — async resolve( request: MatchRequest, context: MatchContext, ): Promise<MatchResult>
- create · method · L155-L202 — private async create( external: Participant[], domain: string, request: MatchRequest, ): Promise<MatchResult>
- createContact · method · L204-L299 — private async createContact( external: Participant[], domain: string, companyId: string, request: MatchRequest, ): Promise<string | null>
