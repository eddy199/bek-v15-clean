# bek-v15-clean/apps/api/src/conversations/conversation-sharing.service.ts

- ConversationSharingService · class · L14-L239 — class ConversationSharingService
- constructor · method · L15-L15 — constructor(@InjectDatabase() private readonly db: Db)
- status · method · L17-L34 — async status(conversationId: string, userId: string)
- create · method · L36-L59 — async create(conversationId: string, userId: string)
- revoke · method · L61-L77 — async revoke(conversationId: string, userId: string)
- resolve · method · L79-L184 — async resolve(token: string, userId: string)
- ownedBuilder · method · L186-L197 — private async ownedBuilder(conversationId: string, userId: string)
- lockOwnedBuilder · method · L199-L217 — private async lockOwnedBuilder( tx: Prisma.TransactionClient, conversationId: string, userId: string, ): Promise<boolean>
- missingBuilder · method · L219-L223 — private missingBuilder(conversationId: string): never
- assertWorkspaceMember · method · L225-L238 — private async assertWorkspaceMember(userId: string): Promise<void>
