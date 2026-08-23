# bek-v15-clean/apps/api/src/conversations/conversation-attachments.controller.ts

- CrmSession · type · L14-L14 — type CrmSession = UserSession<typeof auth>;
- ConversationAttachmentsController · class · L17-L49 — class ConversationAttachmentsController
- constructor · method · L18-L18 — constructor(private readonly conversations: ConversationsService)
- read · method · L21-L48 — async read( @Param("id") id: string, @Query("share") shareToken: string | undefined, @Session() session: CrmSession, @Res({ passthrough: true }) response: Response, )
- encodeHeaderValue · function · L51-L56 — function encodeHeaderValue(value: string): string
