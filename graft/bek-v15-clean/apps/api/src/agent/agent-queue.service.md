# bek-v15-clean/apps/api/src/agent/agent-queue.service.ts

- AgentQueueService · class · L6-L51 — class AgentQueueService
- constructor · method · L7-L7 — constructor(@InjectDatabase() private readonly db: Db)
- queuedCompanies · method · L9-L11 — async queuedCompanies(ids: readonly string[]): Promise<Set<string>>
- queuedContacts · method · L13-L15 — async queuedContacts(ids: readonly string[]): Promise<Set<string>>
- isQueued · method · L17-L31 — async isQueued(subject: { companyId?: string; contactId?: string; }): Promise<boolean>
- queued · method · L33-L50 — private async queued( column: "companyId" | "contactId", ids: readonly string[], ): Promise<Set<string>>
