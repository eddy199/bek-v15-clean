# bek-v15-clean/apps/api/src/tracking/tracking-config.service.ts

- CompiledConfig · interface · L18-L21 — interface CompiledConfig
- TrackingConfigService · class · L24-L133 — class TrackingConfigService
- constructor · method · L29-L32 — constructor( @InjectDatabase() private readonly db: Db, @Inject(CACHE_MANAGER) private readonly cache: Cache, )
- compiled · method · L34-L49 — async compiled(): Promise<CompiledConfig | null>
- current · method · L51-L58 — private async current(hash: string): Promise<boolean>
- forSite · method · L60-L63 — async forSite(siteId: string): Promise<CompiledConfig | null>
- invalidate · method · L65-L93 — async invalidate(): Promise<void>
- ensureSiteId · method · L95-L116 — async ensureSiteId(): Promise<string>
- rotateSiteId · method · L118-L132 — async rotateSiteId(): Promise<string>
