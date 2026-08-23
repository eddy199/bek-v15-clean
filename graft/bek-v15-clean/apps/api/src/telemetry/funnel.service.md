# bek-v15-clean/apps/api/src/telemetry/funnel.service.ts

- FunnelService · class · L16-L162 — class FunnelService
- constructor · method · L19-L19 — constructor(@InjectDatabase() private readonly db: Db)
- sweep · method · L21-L43 — async sweep(): Promise<Milestone[]>
- when · method · L45-L126 — private async when(step: Milestone): Promise<Date | null>
- firstApplied · method · L128-L153 — private async firstApplied(): Promise<Date | null>
- earliest · method · L155-L161 — private async earliest<T>( query: PromiseLike<T | null>, pick: (row: T) => Date | null, ): Promise<Date | null>
