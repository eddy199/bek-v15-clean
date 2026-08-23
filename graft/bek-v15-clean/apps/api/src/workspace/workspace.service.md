# bek-v15-clean/apps/api/src/workspace/workspace.service.ts

- Workspace · interface · L36-L45 — interface Workspace
- WorkspaceMember · interface · L47-L56 — interface WorkspaceMember
- MemberRow · type · L66-L66 — type MemberRow = Prisma.MemberGetPayload<{ select: typeof MEMBER_SELECT }>;
- toRole · function · L78-L80 — function toRole(value: string): WorkspaceRole
- WorkspaceService · class · L83-L302 — class WorkspaceService
- constructor · method · L86-L89 — constructor( @InjectDatabase() private readonly db: Db, private readonly agent: AgentTriggerService, )
- get · method · L91-L117 — async get(userId: string): Promise<Workspace>
- update · method · L119-L166 — async update( userId: string, input: UpdateWorkspaceInput, ): Promise<Workspace>
- members · method · L168-L196 — async members( userId: string, input: MemberListInput, ): Promise<ListResult<WorkspaceMember>>
- setMemberRole · method · L198-L249 — async setMemberRole( userId: string, input: SetMemberRoleInput, ): Promise<WorkspaceMember>
- toMember · method · L251-L262 — private toMember(row: MemberRow, userId: string): WorkspaceMember
- searchWhere · method · L264-L278 — private searchWhere(q: string): Prisma.MemberWhereInput
- buildWhere · method · L280-L288 — private buildWhere(input: MemberListInput): Prisma.MemberWhereInput
- readWorkspace · method · L290-L301 — private async readWorkspace()
