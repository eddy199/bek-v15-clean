# bek-v15-clean/apps/api/src/google/conversation.service.ts

- ConversationService · class · L6-L143 — class ConversationService
- constructor · method · L7-L7 — constructor(@InjectDatabase() private readonly db: Db)
- thread · method · L9-L66 — async thread(threadId: string)
- facesFor · method · L68-L96 — private async facesFor(addresses: string[]): Promise<Map<string, string>>
- event · method · L98-L142 — async event(eventId: string)
- recipientsOf · function · L145-L163 — function recipientsOf( value: unknown, ): { email: string; name: string | null; kind: string }[]
