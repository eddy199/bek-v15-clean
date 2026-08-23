# bek-v15-clean/apps/api/src/google/google.router.ts

- GoogleRouter · class · L25-L85 — class GoogleRouter
- constructor · method · L26-L32 — constructor( @Inject(GoogleConnectionService) private readonly connection: GoogleConnectionService, @Inject(GoogleSyncService) private readonly sync: GoogleSyncService, @Inject(ConversationService) private readonly conversations: ConversationService, )
- status · method · L35-L37 — async status(@Ctx() ctx: AuthedTrpcContext)
- purgeSyncedData · method · L40-L42 — async purgeSyncedData(@Ctx() ctx: AuthedTrpcContext)
- revokeAccess · method · L45-L47 — async revokeAccess(@Ctx() ctx: AuthedTrpcContext)
- syncNow · method · L50-L53 — async syncNow(@Ctx() ctx: AuthedTrpcContext)
- setAutoCreate · method · L56-L66 — async setAutoCreate( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof setAutoCreateInput>, )
- suppressDomain · method · L69-L74 — async suppressDomain(@Input() input: z.infer<typeof suppressDomainInput>)
- thread · method · L77-L79 — async thread(@Input("threadId") threadId: string)
- event · method · L82-L84 — async event(@Input("eventId") eventId: string)
