# bek-v15-clean/apps/api/src/tracking/tracking.controller.ts

- TrackingController · class · L39-L94 — class TrackingController
- constructor · method · L42-L45 — constructor( private readonly config: TrackingConfigService, private readonly ingest: TrackingIngestService, )
- publicConfig · method · L49-L57 — async publicConfig(@Param("siteId") siteId: string)
- collect · method · L62-L93 — async collect( @Req() request: IncomingMessage, @Res({ passthrough: true }) response: Response, @Headers("origin") origin?: string, @Headers("user-agent") userAgent?: string, ): Promise<void>
- TrackingRetentionController · class · L97-L200 — class TrackingRetentionController
- constructor · method · L101-L108 — constructor( @InjectDatabase() private readonly db: Db, private readonly rollups: TrackingRollupService, private readonly counters: TrackingCounterService, config: ConfigService<EnvironmentVariables, true>, )
- viaGet · method · L112-L114 — async viaGet(@Headers("authorization") authorization?: string)
- viaPost · method · L118-L120 — async viaPost(@Headers("authorization") authorization?: string)
- run · method · L122-L163 — private async run(authorization?: string)
- sweepEvents · method · L165-L185 — private async sweepEvents( before: Date, ): Promise<{ removed: number; complete: boolean }>
- sweepVisitors · method · L187-L199 — private async sweepVisitors(before: Date): Promise<number>
- read · function · L202-L238 — async function read( request: IncomingMessage, limit: number, ): Promise<string | null>
- finish · function · L219-L223 — finish = (value: string | null)
- startOfDay · function · L240-L245 — function startOfDay(at: Date): Date
- timingSafeEquals · function · L247-L256 — function timingSafeEquals(a: string, b: string): boolean
