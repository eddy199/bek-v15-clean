# bek-v15-clean/apps/api/src/activities/activities.service.ts

- ActivitiesService · class · L68-L246 — class ActivitiesService
- constructor · method · L71-L74 — constructor( @InjectDatabase() private readonly db: Db, private readonly stamp: ActivityStampService, )
- timeline · method · L76-L98 — async timeline(input: TimelineInput)
- timelineCounts · method · L100-L123 — async timelineCounts( input: Pick<TimelineInput, "companyId" | "contactId" | "dealId">, )
- create · method · L125-L157 — async create(input: ActivityCreateInput, actingUserId: string)
- complete · method · L159-L180 — async complete(id: string, completed: boolean)
- myTasks · method · L182-L204 — async myTasks(input: MyTasksInput, actingUserId: string)
- anchor · method · L206-L215 — private anchor( input: Pick<TimelineInput, "companyId" | "contactId" | "dealId">, ): Prisma.ActivityWhereInput
- resolveCompanyId · method · L217-L245 — private async resolveCompanyId( input: ActivityCreateInput, ): Promise<string | null>
- filterClause · function · L248-L265 — function filterClause(filter: TimelineFilter): Prisma.ActivityWhereInput
- Entry · type · L267-L267 — type Entry = Prisma.ActivityGetPayload<{ select: typeof ENTRY_SELECT }>;
- serializeEntry · function · L269-L298 — function serializeEntry(entry: Entry)
- parseDate · function · L300-L307 — function parseDate(value: string | null | undefined): Date | null
