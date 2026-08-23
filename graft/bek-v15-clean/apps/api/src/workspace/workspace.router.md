# bek-v15-clean/apps/api/src/workspace/workspace.router.ts

- WorkspaceRouter · class · L22-L55 — class WorkspaceRouter
- constructor · method · L23-L25 — constructor( @Inject(WorkspaceService) private readonly workspace: WorkspaceService, )
- get · method · L28-L30 — async get(@Ctx() ctx: AuthedTrpcContext)
- members · method · L33-L38 — async members( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof memberListInput>, )
- update · method · L41-L46 — async update( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof updateWorkspaceInput>, )
- setMemberRole · method · L49-L54 — async setMemberRole( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof setMemberRoleInput>, )
