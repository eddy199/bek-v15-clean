# bek-v15-clean/apps/api/src/dashboard/dashboard.router.ts

- DashboardRouter · class · L11-L23 — class DashboardRouter
- constructor · method · L12-L14 — constructor( @Inject(DashboardService) private readonly dashboard: DashboardService, )
- summary · method · L17-L22 — async summary( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof dashboardSummaryInput>, )
