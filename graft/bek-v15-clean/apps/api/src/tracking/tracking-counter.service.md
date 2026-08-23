# bek-v15-clean/apps/api/src/tracking/tracking-counter.service.ts

- TrackingCounterService · class · L7-L59 — class TrackingCounterService
- constructor · method · L10-L10 — constructor(@InjectDatabase() private readonly db: Db)
- take · method · L12-L35 — async take(key: string, limit: number, amount = 1): Promise<boolean>
- release · method · L37-L50 — async release(key: string, amount = 1): Promise<void>
- sweep · method · L52-L58 — async sweep(): Promise<number>
