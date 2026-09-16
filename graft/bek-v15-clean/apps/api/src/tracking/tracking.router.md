# bek-v15-clean/apps/api/src/tracking/tracking.router.ts

- TrackingRouter · class · L26-L95 — class TrackingRouter
- constructor · method · L27-L29 — constructor( @Inject(TrackingService) private readonly tracking: TrackingService, )
- settings · method · L32-L34 — async settings(@Ctx() ctx: AuthedTrpcContext)
- setFlag · method · L37-L42 — async setFlag( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof trackingFlagInput>, )
- setCookieLifetime · method · L45-L50 — async setCookieLifetime( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof cookieLifetimeInput>, )
- addDomain · method · L53-L58 — async addDomain( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof addDomainInput>, )
- removeDomain · method · L61-L66 — async removeDomain( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof removeDomainInput>, )
- rotateSiteId · method · L69-L71 — async rotateSiteId(@Ctx() ctx: AuthedTrpcContext)
- verify · method · L74-L79 — async verify( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof verifyInput>, )
- sources · method · L82-L84 — async sources(@Ctx() ctx: AuthedTrpcContext)
- companyActivity · method · L87-L89 — async companyActivity(@Input() input: z.infer<typeof companyActivityInput>)
- contactActivity · method · L92-L94 — async contactActivity(@Input() input: z.infer<typeof contactActivityInput>)
