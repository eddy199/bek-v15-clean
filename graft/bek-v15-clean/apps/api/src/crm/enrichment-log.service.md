# bek-v15-clean/apps/api/src/crm/enrichment-log.service.ts

- EnrichmentEvent · type · L6-L12 — type EnrichmentEvent = { companyId?: string | null; contactId?: string | null; subject: string; body?: string | null; meta?: Record<string, unknown>; };
- EnrichmentLogService · class · L15-L67 — class EnrichmentLogService
- constructor · method · L16-L19 — constructor( @InjectDatabase() private readonly db: Db, private readonly stamp: ActivityStampService, )
- record · method · L21-L45 — async record(event: EnrichmentEvent): Promise<string | null>
- authorFor · method · L47-L66 — private async authorFor(event: EnrichmentEvent): Promise<string | null>
- describeFilled · function · L69-L75 — function describeFilled(fields: readonly string[]): string | null
