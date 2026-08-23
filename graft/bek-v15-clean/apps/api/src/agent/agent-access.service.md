# bek-v15-clean/apps/api/src/agent/agent-access.service.ts

- AgentAccessService · class · L18-L99 — class AgentAccessService
- constructor · method · L19-L19 — constructor(@InjectDatabase() private readonly db: Db)
- assertMember · method · L21-L29 — async assertMember(userId: string): Promise<WorkspaceRole>
- assertCanManageInTransaction · method · L31-L75 — async assertCanManageInTransaction( tx: Prisma.TransactionClient, agentId: string, userId: string, )
- assertCanRead · method · L77-L98 — async assertCanRead(agentId: string, userId: string)
