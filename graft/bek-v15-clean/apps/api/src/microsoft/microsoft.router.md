# bek-v15-clean/apps/api/src/microsoft/microsoft.router.ts

- MicrosoftRouter · class · L19-L60 — class MicrosoftRouter
- constructor · method · L20-L25 — constructor( @Inject(MicrosoftConnectionService) private readonly connection: MicrosoftConnectionService, @Inject(MicrosoftSyncService) private readonly sync: MicrosoftSyncService, )
- status · method · L28-L30 — async status(@Ctx() ctx: AuthedTrpcContext)
- purgeSyncedData · method · L33-L35 — async purgeSyncedData(@Ctx() ctx: AuthedTrpcContext)
- revokeAccess · method · L38-L40 — async revokeAccess(@Ctx() ctx: AuthedTrpcContext)
- syncNow · method · L43-L46 — async syncNow(@Ctx() ctx: AuthedTrpcContext)
- setAutoCreate · method · L49-L59 — async setAutoCreate( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof setOutlookAutoCreateInput>, )
