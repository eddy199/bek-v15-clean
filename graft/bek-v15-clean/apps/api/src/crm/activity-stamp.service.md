# bek-v15-clean/apps/api/src/crm/activity-stamp.service.ts

- ActivityTarget · type · L5-L9 — type ActivityTarget = { companyId?: string | null; contactId?: string | null; dealId?: string | null; };
- StampTargets · type · L11-L15 — type StampTargets = { companyIds: string[]; contactIds: string[]; dealIds: string[]; };
- present · function · L17-L19 — function present(ids: (string | null)[]): string[]
- ActivityStampService · class · L22-L190 — class ActivityStampService
- constructor · method · L25-L25 — constructor(@InjectDatabase() private readonly db: Db)
- touch · method · L27-L52 — async touch(target: ActivityTarget, at: Date): Promise<void>
- recompute · method · L54-L87 — async recompute(target: ActivityTarget): Promise<void>
- targetsOf · method · L89-L104 — async targetsOf( where: Prisma.ActivityWhereInput, client: Prisma.TransactionClient = this.db, ): Promise<StampTargets>
- recomputeMany · method · L106-L116 — async recomputeMany(targets: StampTargets): Promise<void>
- recomputeAfterDelete · method · L118-L134 — async recomputeAfterDelete( targets: StampTargets, deleted: ActivityTarget, ): Promise<void>
- restamp · method · L136-L148 — private restamp(table: string, column: string, ids: string[])
- recomputeAll · method · L150-L189 — async recomputeAll(): Promise<void>
